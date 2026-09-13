# PDF source processing

Use the MinerU hosted service for PDF content extraction in this project,
including TI reference designs and component datasheets. Use the
`mineru-service` skill when available; otherwise follow the official hosted API
documentation at https://mineru.net/doc/docs/index_en/.

For engineering extraction, prefer the precision VLM service with formula and
table recognition. Preserve original PDFs, source revisions, hashes, returned
artifacts, and page or figure references. Keep tokens and signed URLs out of
source control and logs. Missing credentials must be reported before claiming
precision extraction has run.

Local PDF rendering may be used for visual verification. Do not silently
substitute a local parser for the requested MinerU service. Parsed schematic
images and OCR are not validated netlists; check connectivity, units and
critical values against the source before encoding expert modules.
