# Complete Flow: Responding to a Search Query

This document traces the flow when **we** (the client) respond to a search query from another client and handle their subsequent download request.

## Overview

When another client searches for files and we have matching results, we respond with our files and potentially upload them. This trace follows the complete message flow from receiving the search query through file transfer.

---

## Flow Steps

### Step 1: Receive FileSearch Message from Server

**Message**: `FileSearch` (Server code 26)
**Source**: Server → Us
**Handler**: `pynicotine/search.py:460` (`_file_search_request_server`)

The server receives a search query from another user and propagates it to us through the network.

**Message Contents:**
- `username`: The searching user's username
- `token`: A unique token for tracking this search
- `searchterm`: The search query string

```python
def _file_search_request_server(self, msg):
    """Server code 26."""
    self._process_search_request(msg.searchterm, msg.search_username, msg.token)
    core.pluginhandler.search_request_notification(msg.searchterm, msg.search_username, msg.token)
```

**Alternative:** We might also receive `DistribSearch` (Distributed code 3) through the distributed network:
- **Handler**: `pynicotine/search.py:466` (`_file_search_request_distributed`)
- Same processing, just different propagation path

---

### Step 2: Process Search Request

**Method**: `search.py:646` (`_process_search_request`)

We check if we should respond to this search query:

1. **Validation checks:**
   - Config allows search results (`config.sections["searches"]["search_results"]`)
   - Not in pending shutdown mode
   - Search term meets minimum length requirement
   - User is not banned
   - We're not searching ourselves (unless specifically requested)

2. **Search our shared files:**
   - Parse search term into included/excluded/partial words
   - Query our word index database (`core.shares.share_dbs["words"]`)
   - Find file matches using set intersections
   - Limit results to configured maximum

3. **Build file info lists:**
   - Separate public and private shares
   - Check user permission level (public/buddy/trusted)
   - Collect file paths, sizes, and attributes

**Code location**: `search.py:646-755`

---

### Step 3: Send FileSearchResponse Message

**Message**: `FileSearchResponse` (Peer code 9)
**Direction**: Us → Searcher (peer-to-peer)
**Sent from**: `search.py:735`

If we have matching files, we send a response directly to the searching user:

```python
core.send_message_to_peer(username, FileSearchResponse(
    search_username=local_username,
    token=token,
    shares=fileinfos,
    freeulslots=core.uploads.is_new_upload_accepted(),
    ulspeed=core.uploads.upload_speed,
    inqueue=core.uploads.get_upload_queue_size(username),
    private_shares=private_fileinfos
))
```

**Message Contents:**
- Our username
- Search token (same as received)
- List of matching files (compressed with zlib)
- Upload slot availability
- Our upload speed
- Queue position for this user

**Connection Type**: `P` (Peer-to-Peer)
**Protocol handler**: `slskproto.py:707` (`_send_message_to_peer`)

**Connection Establishment:**
When sending this message, if no P connection exists:
1. Try to get peer's address from cache
2. If not cached, request from server via `GetPeerAddress`
3. Attempt direct connection via `PeerInit`
4. If direct fails, request indirect connection via `ConnectToPeer`

---

### Step 4: Receive QueueUpload Message

**Message**: `QueueUpload` (Peer code 43)
**Direction**: Searcher → Us
**Handler**: `uploads.py:918` (`_queue_upload`)

If the searcher wants to download a file, they send us a queue upload request:

```python
def _queue_upload(self, msg):
    """Peer code 43.

    Peer remotely queued a download (upload here). This is the
    modern replacement to a TransferRequest with direction 0.
    We will initiate the upload of the queued file later.
    """
```

**Processing:**
1. Validate the file exists and is shared
2. Check user permissions (not banned, allowed to download)
3. Handle edge cases (lowercase paths, backslash paths)
4. Add to our upload queue
5. Assign queue position
6. Update transfer tracking

**Code location**: `uploads.py:918-989`

**Note:** Legacy clients may send `TransferRequest` with direction=0 instead. This is handled by `uploads.py:991` (`_transfer_request`).

---

### Step 5: Send TransferRequest Message

**Message**: `TransferRequest` (Peer code 40)
**Direction**: Us → Downloader
**Sent from**: `uploads.py:628-631`

When we're ready to upload (slot available, user's turn in queue):

```python
core.send_message_to_peer(
    username, TransferRequest(
        direction=TransferDirection.UPLOAD,  # direction = 1
        token=self.token,
        file=virtual_path,
        filesize=final_upload_candidate.size
    ))
```

**Message Contents:**
- `direction`: 1 (UPLOAD to peer)
- `token`: Our generated token for this transfer
- `file`: Virtual file path
- `filesize`: File size in bytes

**Connection Type**: `P` (Peer-to-Peer) - reuses existing connection

---

### Step 6: Receive TransferResponse Message

**Message**: `TransferResponse` (Peer code 41)
**Direction**: Downloader → Us
**Handler**: `uploads.py:1075` (`_transfer_response`)

The downloader responds, either accepting or rejecting:

```python
def _transfer_response(self, msg):
    """Peer code 41.

    Received a response to the file request from the peer
    """
```

**If Accepted** (`msg.allowed == True`):
- Proceed to step 7 (file transfer init)

**If Rejected** (`msg.reason` provided):
- Abort transfer with reason
- Check upload queue for next transfer
- Common reasons: "Cancelled", "Complete", "Queued", etc.

**Code location**: `uploads.py:1075-1117`

---

### Step 7: Initiate File Transfer Connection

**Message**: `FileTransferInit` (File message)
**Direction**: Us → Downloader
**Sent from**: `uploads.py:1115`

When transfer is accepted, we initiate an **F** (File) connection:

```python
core.send_message_to_peer(
    upload.username,
    FileTransferInit(token=token, is_outgoing=True)
)
```

**Connection Establishment** (handled by `slskproto.py:707-744`):

Since `FileTransferInit.msg_type = MessageType.FILE = "F"`:

1. Check for existing F connection to user
2. If none exists, initiate new F connection:
   - Get peer's address (from cache or via `GetPeerAddress`)
   - Attempt **direct connection**: Send `PeerInit` with type='F'
   - If direct fails, attempt **indirect connection**:
     - Send `ConnectToPeer` to server with type='F'
     - Server forwards to downloader
     - Downloader receives `ConnectToPeer` and connects to us
     - Downloader sends `PierceFireWall` to complete connection

**Protocol**: Modern Peer Connection Message Order (SLSKPROTOCOL.md:2303-2331)

---

### Step 8: File Transfer Begins

**Handler**: `uploads.py:1148` (`_file_transfer_init`)

Once the F connection is established and `FileTransferInit` is sent:

```python
def _file_transfer_init(self, msg):
    """We are requesting to start uploading a file to a peer."""
```

**Process:**
1. Verify upload is active and pending
2. Open the file for reading
3. Set transfer start time
4. Begin sending file data in chunks
5. Track upload progress via `_file_upload_progress` events
6. Handle errors with `_upload_file_error`

**File Transfer:**
- Data sent over F connection in small chunks
- No message codes - raw file data
- Downloader may send `FileOffset` to resume partial download
- Transfer continues until complete or connection drops

**Code location**: `uploads.py:1148-1217`

---

### Step 9: Transfer Completion or Failure

**Success:**
- Transfer completes successfully
- `_finish_transfer` called
- Check upload queue for next transfer
- Update statistics

**Failure:**
- Send `UploadFailed` (Peer code 46) to downloader
- Transfer re-queued or aborted depending on reason
- Check upload queue for next transfer

**Handler**: `uploads.py:1129` (`_upload_file_error`)

---

## Key Code Locations

| Component | File | Lines |
|-----------|------|-------|
| Receive FileSearch | `search.py` | 460-464 |
| Process Search | `search.py` | 646-755 |
| Send FileSearchResponse | `search.py` | 735-743 |
| Receive QueueUpload | `uploads.py` | 918-989 |
| Send TransferRequest | `uploads.py` | 628-631 |
| Receive TransferResponse | `uploads.py` | 1075-1117 |
| Send FileTransferInit | `uploads.py` | 1115 |
| File Transfer Init Handler | `uploads.py` | 1148-1217 |
| Peer Connection Handler | `slskproto.py` | 707-855 |
| ConnectToPeer Handler | `slskproto.py` | 1275-1285 |

---

## Message Types Summary

| Message | Code | Type | Direction | Purpose |
|---------|------|------|-----------|---------|
| FileSearch | Server 26 | Server | Server→Us | Search query propagation |
| FileSearchResponse | Peer 9 | Peer (P) | Us→Searcher | Send matching files |
| QueueUpload | Peer 43 | Peer (P) | Searcher→Us | Request file download |
| TransferRequest | Peer 40 | Peer (P) | Us→Downloader | Ready to upload |
| TransferResponse | Peer 41 | Peer (P) | Downloader→Us | Accept/reject transfer |
| FileTransferInit | - | File (F) | Us→Downloader | Start file transfer |
| PierceFireWall | Init 0 | Init | Variable | Complete indirect connection |
| ConnectToPeer | Server 18 | Server | Server↔Both | Indirect connection request |

---

## Critical Discrepancies with Documentation

### Discrepancy #1: Search Result Connection Flow

**Documentation** (SLSKPROTOCOL.md:2998):
> "3. We receive a ConnectToPeer message from the server for any peers that have a match for the search query."

**Reality in Code:**
- After a `FileSearch` is propagated, responding peers send `FileSearchResponse` **directly** via peer-to-peer connection
- `ConnectToPeer` is **only** received if:
  1. A direct P connection cannot be established, OR
  2. Later for the F (file transfer) connection (step 8 of documented flow)

**Why This is Misleading:**
- The documentation implies ConnectToPeer is automatically sent for search results
- In practice, peers establish P connections on-demand
- ConnectToPeer is a fallback mechanism for failed direct connections

**Correct Flow:**
1. Peer receives `FileSearch`
2. Peer calls `send_message_to_peer` with `FileSearchResponse`
3. If no P connection exists:
   - Try `GetPeerAddress` → direct `PeerInit`
   - Only if direct fails → `ConnectToPeer` (indirect)
4. `FileSearchResponse` sent over established P connection

### Discrepancy #2: FileTransferInit Connection Initiation

**Documentation** (SLSKPROTOCOL.md:3008-3011):
> "8. We receive a ConnectToPeer message from the server with the username of the peer, this time with an F connection.
> 9. We send a PierceFireWall message to the peer..."

**Reality in Code:**
- **Uploader** (us) initiates the F connection when sending `FileTransferInit`
- **Downloader** receives `ConnectToPeer` if indirect connection needed
- The documentation presents this from the downloader's perspective

**From Uploader's Perspective (Our Flow):**
1. We send `FileTransferInit` via `send_message_to_peer`
2. This triggers F connection establishment
3. We send `ConnectToPeer` to server (if indirect)
4. Server forwards to downloader
5. Downloader either:
   - Accepts our direct `PeerInit`, OR
   - Sends us `PierceFireWall` for indirect connection

### Discrepancy #3: Connection Type for FileSearchResponse

**Documentation** (SLSKPROTOCOL.md:2533):
> "FileSearchResponse: A peer sends this message when it has a file search match."

**Code Reality** (`slskmessages.py:3216`):
- `FileSearchResponse` is a `PeerMessage` with `msg_type = MessageType.PEER = "P"`
- Sent over P (peer-to-peer) connection
- May require establishing new P connection
- Connection establishment follows Modern/Legacy Peer Connection Message Order

**Important:** The documentation correctly notes this is a peer message but doesn't emphasize that it requires active connection establishment, which may involve ConnectToPeer as a fallback.

---

## Connection Types

| Type | Letter | Purpose | Initiated By |
|------|--------|---------|--------------|
| Peer | P | Search responses, chat, browsing | Either party |
| File | F | File transfers | Uploader |
| Distributed | D | Distributed search network | Parent/child peers |
| Server | S | Server communication | Client |

---

## Flow Diagram (ASCII)

```
[Server]
    │
    │ 1. FileSearch (Server code 26)
    │    (Another user is searching)
    ▼
  [Us]
    │
    │ 2. Process search
    │    - Check word index
    │    - Find matches
    │    - Build file list
    │
    │ 3. FileSearchResponse (Peer code 9) [P connection]
    │────────────────────────────────────────────────────►[Searcher]
    │                                                      │
    │                                                      │ (Decides to download)
    │                                                      │
    │ 4. QueueUpload (Peer code 43) [P connection]        │
    │◄────────────────────────────────────────────────────│
    │                                                      │
    │ (Add to queue, wait for slot)                       │
    │                                                      │
    │ 5. TransferRequest (Peer code 40) [P connection]    │
    │    direction=UPLOAD, token, file, size              │
    │────────────────────────────────────────────────────►│
    │                                                      │
    │                                                      │ (Accept/Reject)
    │                                                      │
    │ 6. TransferResponse (Peer code 41) [P connection]   │
    │    allowed=True/False, reason                       │
    │◄────────────────────────────────────────────────────│
    │                                                      │
    │ 7. FileTransferInit [F connection establishment]    │
    │    - Send ConnectToPeer to server (if indirect)     │
    │    - Or direct PeerInit with type='F'               │
    │                                                      │
    │ [F Connection Established]                          │
    │━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━│
    │                                                      │
    │ 8. File Data Transfer [F connection]                │
    │    - Raw file chunks                                │
    │    - No message codes                               │
    │════════════════════════════════════════════════════►│
    │                                                      │
    │                                                      │
    │ 9. Transfer Complete                                │
    │    (or UploadFailed on error)                       │
    │                                                      │
```

---

## Notes

1. **Token Management**:
   - Search tokens are managed by `SEARCH_TOKENS_ALLOWED` global set
   - Transfer tokens are managed per-upload with `increment_token()`
   - Tokens must match across request/response pairs

2. **Connection Reuse**:
   - P connections persist for multiple messages
   - F connections are per-transfer
   - New P connection established if needed for search response

3. **Legacy Compatibility**:
   - Old clients may use `TransferRequest(direction=0)` instead of `QueueUpload`
   - Handler supports both: `uploads.py:991` (`_transfer_request`)

4. **Distributed Search**:
   - Alternative to server FileSearch
   - Propagates through parent/child peer network
   - Same processing on our end

5. **Error Handling**:
   - Multiple abort paths (banned users, missing files, etc.)
   - `UploadFailed` message notifies peer
   - Queue automatically processed for next transfer

---

## Comparison: Documentation vs. Code

**Documentation (SLSKPROTOCOL.md:2993-3018) - From DOWNLOADER perspective:**
1. Send FileSearch to server
2. Server propagates search
3. **Receive ConnectToPeer for peers with matches** ⚠️
4. Expect FileSearchResponse
5. Send QueueUpload
6. Receive TransferRequest
7. Send TransferResponse (accept)
8. Receive ConnectToPeer with F connection
9. Send PierceFireWall
10. Receive file data
11. Transfer complete

**Code Reality - From UPLOADER perspective (responding to search):**
1. ✅ Receive FileSearch from server
2. ✅ Process search locally
3. ✅ Send FileSearchResponse (P connection, may need ConnectToPeer as fallback)
4. ✅ Receive QueueUpload
5. ✅ Send TransferRequest
6. ✅ Receive TransferResponse
7. ✅ Send FileTransferInit (initiates F connection)
8. ✅ Establish F connection (may send ConnectToPeer to server)
9. ✅ Send file data
10. ✅ Transfer complete

**Key Difference**: Step 3 in documentation is misleading - ConnectToPeer is not automatically sent for search results. It's only used as a fallback for connection establishment failures.

---

## Conclusion

The code implements a sophisticated peer-to-peer file sharing protocol with:
- Direct and indirect connection fallbacks
- Multiple connection types (P, F, D)
- Robust error handling
- Queue management
- Legacy client compatibility

The main discrepancy between code and documentation is the oversimplification of the connection establishment process for search responses. The protocol is more nuanced, with ConnectToPeer serving as a fallback mechanism rather than a primary flow step.
