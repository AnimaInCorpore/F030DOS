# PacketLoad — Origin packet section loader

Status: **Unproven** as a DOS function record. The packet bytes and the Falcon
fixture are verified, but the canonical 1990 DOS entry/range and a direct DOS
execution fixture have not yet been recovered. The new `0xFF` branch therefore
must not be used to claim a newly supported game path.

## DOS identity and evidence

- Authority image: `release/WC1DATA/WC.EXE`, SHA-256
  `576359ede27e6ff3d973d5f6b9db2e79f640fd2a883386268952ccf3c2445f78`.
- Canonical DOS symbol and range: **TBD**. The 1990 stripped image has not
  yet been mapped to a verified packet-loader entry.
- Supporting evidence only: `../wc1-re/src/pload.c` labels a 1996 Kilrathi
  Saga Win32 function `PacketLoad`, with a provisional entry at `0x42B050`.
  That build is not the authority for this port and its address is not a DOS
  address for this record.
- Data authority for the new branch: the verified Origin packet directory
  rule in `analysis/data-formats.md` §2.2. In the staged `PCSHIP.V04`
  (`5c38b7cddee1970249e25db68f63cb94fc3f47a070e494a5fa29357057264a4f`),
  section 1 has compression byte `0xFF` and the next directory offset repeats
  the same section offset, proving a zero-length fixed-index hole.

## Recovered/implemented contract

The target seam accepts a DOS-style staged filename and 16-bit section index.
It reads the packet header and directory as little-endian 32-bit values,
derives the section end from the next directory entry (or the declared file
size for the last section), and publishes:

- `resource_packet_compression`: the directory compression byte;
- `resource_packet_size`: decoded or raw byte count; and
- `resource_packet_data`: the bounded raw or decoded section buffer.

For a verified `0xFF` entry, the target requires
`directory_size <= section_offset == section_end <= declared_size`, performs
no payload read, leaves `resource_packet_size == 0`, preserves the compression
byte, and returns success. Raw (`0`) and Origin LZW (`1`) sections retain their
existing bounded paths. Invalid ranges, unsupported compression values, and
failed I/O return failure.

The zero-length interpretation is proven from the shipped packet bytes. Its
equivalence to the 1990 DOS routine's return/error convention remains
**Unproven** until the DOS function is disassembled and exercised.

## Implementations and fixtures

- Browser/JavaScript: **none**. No browser counterpart exists yet, so this
  branch is not eligible for a supported browser/target slice.
- Falcon target: `src/resources.c:resource_load_packet()`.
- Host fixture: `tools/resource_loader_smoke.c` calls
  `resource_load_packet("PCSHIP.V04", 1U)` and requires success,
  compression `0x00FF`, and size `0`. Run from `release/` with
  `make resource-smoke`.
- Static seam coverage: `tools/check_contracts.py` requires the absent-section
  constant and fixture call.

## Difference ledger against DOS

| Area | Target behaviour | Evidence/status |
| --- | --- | --- |
| Packet field decoding | Explicit little-endian reads and 24-bit offset masking | Verified from packet headers and §2; target artefact is the C implementation. |
| Absent fixed slot | Accept verified `0xFF`/zero-length entry as an empty successful load | Packet bytes prove the hole; DOS return convention is **Unproven**. |
| Memory ownership | Fixed bounded Falcon buffers; no allocation | Target artefact required by the stock-Falcon memory budget; does not alter valid decoded bytes. |
| Browser reference | No implementation | **Unproven** / open work. |

## Open work

1. Recover the 1990 DOS packet-loader symbol and canonical range from the
   hashed executable and overlay map.
2. Capture a DOS call that reaches an absent `0xFF` resource slot and record
   its return value, error state, and caller handling.
3. Add the JavaScript reference and shared contract fixture before promoting
   the branch into a supported campaign, room, or flight resource path.
