# OmniRAG Universal Intake Gate — Implementation Plan

**Date:** 2026-04-05
**Agent:** Planner
**Status:** Active

---

## Objective

Build a single Universal Intake Gate that accepts **any source** (local, cloud, DB, SaaS, web, streams) and **any data format** (PDF, DOCX, HTML, images, audio, structured data) and normalizes everything into `OmniDocument` objects for the existing OmniRAG pipeline.

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │        INTAKE GATE (single API)      │
                    │   POST /intake                       │
                    │   { source, format?, config }        │
                    └───────────────┬─────────────────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │         SOURCE RESOLVER               │
                    │   Detects source type, authenticates  │
                    │   Dispatches to correct Connector     │
                    └───────────────┬─────────────────────┘
                                    │
        ┌───────────┬───────────┬───┴───┬───────────┬──────────┐
        ▼           ▼           ▼       ▼           ▼          ▼
   ┌─────────┐ ┌─────────┐ ┌───────┐ ┌──────┐ ┌────────┐ ┌────────┐
   │  Local   │ │  Cloud  │ │  Web  │ │  DB  │ │  SaaS  │ │ Stream │
   │Connector │ │Connector│ │Connec.│ │Conn. │ │Connec. │ │Connec. │
   └────┬─────┘ └────┬────┘ └──┬────┘ └──┬───┘ └───┬────┘ └───┬────┘
        │            │         │         │         │          │
        └────────────┴─────────┴────┬────┴─────────┴──────────┘
                                    │
                    ┌───────────────▼─────────────────────┐
                    │         FORMAT DETECTOR               │
                    │   MIME type, extension, magic bytes   │
                    │   Dispatches to correct Loader        │
                    └───────────────┬─────────────────────┘
                                    │
   ┌──────┬──────┬──────┬──────┬────┴──┬──────┬──────┬──────┐
   ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼
 ┌────┐┌────┐┌────┐┌─────┐┌─────┐┌─────┐┌────┐┌─────┐┌─────┐
 │PDF ││DOCX││HTML││Image││Audio││Video││CSV ││JSON ││Code │
 │Load││Load││Load││ OCR ││ STT ││Trans││Load││Load ││Load │
 └──┬─┘└──┬─┘└──┬─┘└──┬──┘└──┬──┘└──┬──┘└──┬─┘└──┬──┘└──┬──┘
    │     │     │     │      │      │      │     │      │
    └─────┴─────┴─────┴──┬───┴──────┴──────┴─────┴──────┘
                         │
                ┌────────▼────────────────────────────────┐
                │           NORMALIZER                     │
                │   Raw text → OmniDocument                │
                │   { id, text, metadata, source, format } │
                └────────────┬────────────────────────────┘
                             │
                ┌────────────▼────────────────────────────┐
                │      EXISTING OMNIRAG PIPELINE           │
                │   chunk → embed → store → retrieve → gen │
                └─────────────────────────────────────────┘
```

---

## Layer 1: Connectors (fetch raw bytes from source)

| Connector | Sources | Auth | Priority |
|-----------|---------|------|----------|
| `local` | filesystem, mounted drives, NFS/SMB | none/OS-level | P0 |
| `http` | any URL, REST APIs, RSS, sitemaps | API key, Bearer, Basic | P0 |
| `s3` | AWS S3, MinIO | AWS credentials | P1 |
| `gcs` | Google Cloud Storage | service account JSON | P1 |
| `azure` | Azure Blob Storage | connection string | P1 |
| `github` | repos (files, issues, PRs, wikis) | PAT, OAuth | P1 |
| `gitlab` | repos, issues | PAT | P2 |
| `postgres` | PostgreSQL tables/queries | connection string | P1 |
| `mysql` | MySQL tables/queries | connection string | P2 |
| `mongodb` | MongoDB collections | connection string | P2 |
| `sqlite` | SQLite files | file path | P1 |
| `elasticsearch` | ES indices | URL + credentials | P2 |
| `redis` | Redis keys/streams | URL | P2 |
| `notion` | Notion pages/databases | integration token | P2 |
| `slack` | channels, threads | Bot token | P2 |
| `confluence` | spaces, pages | API token | P2 |
| `jira` | issues, comments | API token | P2 |
| `gdrive` | Google Drive files | OAuth/service account | P2 |
| `dropbox` | Dropbox files | OAuth token | P3 |
| `onedrive` | OneDrive files | OAuth token | P3 |
| `imap` | email mailboxes | credentials | P2 |
| `gmail` | Gmail messages | OAuth | P2 |
| `kafka` | Kafka topics | broker config | P3 |
| `rabbitmq` | RabbitMQ queues | connection string | P3 |
| `mqtt` | MQTT topics | broker config | P3 |
| `websocket` | WS feeds | URL | P3 |
| `bigquery` | BigQuery tables | service account | P3 |
| `snowflake` | Snowflake tables | credentials | P3 |

### Connector interface:

```python
class BaseConnector(ABC):
    """Fetches raw bytes/text from a source."""

    @abstractmethod
    async def fetch(self, config: dict) -> AsyncIterator[RawContent]:
        """Yields RawContent objects (bytes + metadata)."""

    @abstractmethod
    def supports(self, source_uri: str) -> bool:
        """Returns True if this connector handles the given URI."""
```

---

## Layer 2: Loaders (parse raw bytes into text)

| Loader | Formats | Library | Priority |
|--------|---------|---------|----------|
| `text` | .txt, .md, .rst, .log | built-in | P0 |
| `pdf` | .pdf | PyPDF2 / pdfplumber | P0 |
| `docx` | .docx | python-docx | P0 |
| `html` | .html, .htm | BeautifulSoup | P0 |
| `csv` | .csv, .tsv | built-in csv | P0 |
| `json` | .json, .jsonl | built-in json | P0 |
| `xml` | .xml | ElementTree | P1 |
| `xlsx` | .xlsx | openpyxl | P1 |
| `pptx` | .pptx | python-pptx | P1 |
| `epub` | .epub | ebooklib | P2 |
| `rtf` | .rtf | striprtf | P2 |
| `code` | .py, .ts, .java, .go, etc. | built-in (with language detection) | P1 |
| `notebook` | .ipynb | built-in json | P1 |
| `yaml` | .yaml, .yml, .toml | PyYAML / tomli | P1 |
| `email` | .eml, .mbox | email.parser | P1 |
| `image_ocr` | .png, .jpg, .tiff | Tesseract / EasyOCR | P2 |
| `audio_stt` | .mp3, .wav, .m4a | Whisper / Deepgram | P3 |
| `video_stt` | .mp4, .webm | ffmpeg + Whisper | P3 |
| `parquet` | .parquet | pyarrow | P2 |
| `sql_dump` | .sql | sqlparse | P2 |

### Loader interface:

```python
class BaseLoader(ABC):
    """Parses raw content into text segments."""

    @abstractmethod
    async def load(self, content: RawContent) -> list[TextSegment]:
        """Parses raw bytes into text segments with metadata."""

    @abstractmethod
    def supports(self, mime_type: str, extension: str) -> bool:
        """Returns True if this loader handles the given format."""
```

---

## Layer 3: Normalizer

Converts `TextSegment` objects into `OmniDocument` (existing canonical model):

```python
@dataclass
class OmniDocument:
    id: str                    # unique hash
    text: str                  # extracted text
    metadata: dict             # source, page, section, timestamp, etc.
    source_uri: str            # original source URI
    format: str                # detected format (pdf, docx, html, etc.)
    connector: str             # which connector fetched it
    loader: str                # which loader parsed it
    created_at: datetime       # ingestion timestamp
    chunk_hint: str | None     # suggested chunking strategy
```

---

## Layer 4: Intake Gate API

### Single endpoint:

```
POST /intake
```

### Request body:

```json
{
  "source": "s3://my-bucket/reports/*.pdf",
  "config": {
    "credentials": { "aws_access_key": "...", "aws_secret_key": "..." },
    "recursive": true,
    "max_files": 100
  },
  "pipeline": "pdf_qa",
  "options": {
    "chunk_size": 512,
    "overlap": 50,
    "ocr": false
  }
}
```

### Source URI formats:

```
# Local
file:///path/to/docs/*.pdf
/path/to/docs/*.pdf              (implied file://)

# Cloud
s3://bucket/prefix/
gs://bucket/prefix/
azure://container/prefix/

# Web
https://example.com/page
https://example.com/sitemap.xml
rss://feed.example.com/rss

# Git
github://owner/repo
github://owner/repo/path/to/file
gitlab://owner/repo

# Database
postgres://user:pass@host/db?query=SELECT...
mongodb://host/db/collection
sqlite:///path/to/db.sqlite

# SaaS
notion://page-id
slack://channel-id
confluence://space/page
jira://project/issue

# Email
imap://user:pass@host/INBOX
gmail://me/label/inbox

# Stream
kafka://broker/topic
ws://host/feed
```

### Response:

```json
{
  "intake_id": "int_abc123",
  "status": "processing",
  "source": "s3://my-bucket/reports/*.pdf",
  "files_found": 47,
  "documents_created": 0,
  "pipeline": "pdf_qa"
}
```

### Poll:

```
GET /intake/{intake_id}
```

---

## Implementation Order

### Phase 0 — Core framework (P0)
1. `RawContent` and `TextSegment` dataclasses
2. `BaseConnector` and `BaseLoader` ABCs
3. `ConnectorRegistry` and `LoaderRegistry`
4. `FormatDetector` (MIME + extension + magic bytes)
5. `SourceResolver` (URI parsing → connector dispatch)
6. `Normalizer` (TextSegment → OmniDocument)
7. `IntakeGate` orchestrator class
8. `POST /intake` and `GET /intake/{id}` API routes

### Phase 1 — Essential connectors + loaders
9. `LocalConnector` (filesystem, glob patterns)
10. `HttpConnector` (URL fetch, auth headers)
11. `TextLoader` (txt, md, rst, log)
12. `PdfLoader` (PyPDF2 + pdfplumber)
13. `DocxLoader` (python-docx)
14. `HtmlLoader` (BeautifulSoup)
15. `CsvLoader` + `JsonLoader`
16. `CodeLoader` (source files with language detection)

### Phase 2 — Cloud + database connectors
17. `S3Connector`
18. `GitHubConnector`
19. `PostgresConnector` + `SqliteConnector`
20. `XlsxLoader` + `PptxLoader`
21. `XmlLoader` + `YamlLoader`
22. `EmailLoader` (.eml, .mbox)
23. `NotebookLoader` (.ipynb)

### Phase 3 — SaaS + media + streams
24. `NotionConnector` + `SlackConnector`
25. `ConfluenceConnector` + `JiraConnector`
26. `GDriveConnector`
27. `ImageOcrLoader` (Tesseract)
28. `AudioSttLoader` (Whisper)
29. `KafkaConnector` + `WebSocketConnector`
30. `ParquetLoader` + `SqlDumpLoader`

---

## File Structure

```
omnirag/
  intake/
    __init__.py
    gate.py              # IntakeGate orchestrator
    models.py            # RawContent, TextSegment, IntakeJob
    resolver.py          # SourceResolver (URI → connector)
    detector.py          # FormatDetector (MIME, extension, magic)
    normalizer.py        # TextSegment → OmniDocument
    connectors/
      __init__.py
      base.py            # BaseConnector ABC
      registry.py        # ConnectorRegistry
      local.py           # LocalConnector
      http.py            # HttpConnector
      s3.py              # S3Connector
      github.py          # GitHubConnector
      postgres.py        # PostgresConnector
      sqlite.py          # SqliteConnector
      notion.py          # NotionConnector
      slack.py           # SlackConnector
      ...
    loaders/
      __init__.py
      base.py            # BaseLoader ABC
      registry.py        # LoaderRegistry
      text.py            # TextLoader
      pdf.py             # PdfLoader
      docx.py            # DocxLoader
      html.py            # HtmlLoader
      csv_loader.py      # CsvLoader
      json_loader.py     # JsonLoader
      code.py            # CodeLoader
      xlsx.py            # XlsxLoader
      pptx.py            # PptxLoader
      xml_loader.py      # XmlLoader
      email_loader.py    # EmailLoader
      notebook.py        # NotebookLoader
      image_ocr.py       # ImageOcrLoader
      audio_stt.py       # AudioSttLoader
      ...
  api/
    routes/
      intake.py          # POST /intake, GET /intake/{id}
```

---

## Dependencies (new)

```toml
[project.optional-dependencies]
intake-core = [
  "pdfplumber>=0.10",
  "python-docx>=1.0",
  "beautifulsoup4>=4.12",
  "python-magic>=0.4",
  "chardet>=5.0",
]
intake-cloud = [
  "boto3>=1.34",
  "google-cloud-storage>=2.14",
  "azure-storage-blob>=12.19",
]
intake-db = [
  "asyncpg>=0.29",
  "aiosqlite>=0.20",
  "pymongo>=4.6",
]
intake-saas = [
  "notion-client>=2.2",
  "slack-sdk>=3.27",
]
intake-media = [
  "pytesseract>=0.3",
  "openai-whisper>=20231117",
]
intake-all = [
  "omnirag[intake-core,intake-cloud,intake-db,intake-saas,intake-media]",
]
```
