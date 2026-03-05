# ECFMG Certified Translation Integration

## Overview

The ECFMG (Educational Commission for Foreign Medical Graduates) feature allows users to order certified translations through both the Telegram and WhatsApp bots. It integrates with the Straker Order API to upload documents, create jobs, receive quotes, and generate payment links.

## Architecture

The integration follows the same patterns established by the existing `translate` workflow:

- **Telegram**: Factory-function handler pattern with `ConversationHandler` state machine
- **WhatsApp**: Class-based handler pattern with `ConversationState` enum routing

### Components

| Component | File | Purpose |
|-----------|------|---------|
| OrderClient | `src/order/client.py` | Async HTTP client for the Order API |
| Order Models | `src/order/models.py` | Pydantic models for API request/response |
| TG Handler | `src/bot/handlers/ecfmg.py` | Telegram conversation handler |
| WA Handler | `src/whatsapp_bot/handlers/ecfmg.py` | WhatsApp message handler |
| Keyboards | `src/bot/keyboards.py` | ECFMG inline keyboard builders |
| States | `src/bot/states.py` / `src/whatsapp_bot/states.py` | Conversation state definitions |

### API Flow

1. User provides personal details and selects source language/country (target is fixed to English (USA))
2. User uploads a document
3. User accepts terms and conditions
4. User confirms the order
5. Bot simultaneously calls:
   - `POST /file/save` -- uploads the document with a session token
   - `POST /job` -- creates the ECFMG job with all form data
6. Bot displays the quote summary and payment link

The file upload and job creation share a `session` token (UUID) that correlates them on the server side.

## Conversation Flow

| Step | State | Description |
|------|-------|-------------|
| 1 | Entry | `/ecfmg` command, auth check, session token generated |
| 2 | AWAITING_FIRSTNAME | Collect first name |
| 3 | AWAITING_LASTNAME | Collect last name |
| 4 | AWAITING_EMAIL | Collect and validate email |
| 5 | AWAITING_PHONE | Collect phone number |
| 6 | AWAITING_SOURCE_LANG | Select source language from `/languages?type=ecfmg` |
| 7 | AWAITING_COUNTRY | Select country (paginated, searchable) |
| 8 | AWAITING_FILE | Upload document |
| 9 | AWAITING_TERMS | Accept terms & conditions |
| 10 | AWAITING_NOTES | Optional notes (with skip) |
| 11 | CONFIRM | Review summary, submit or cancel |

Target language is fixed to **English (USA)** (`English_US`) and is not prompted from the user.

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ORDER_BASE_URL` | `https://order.strakertranslations.com` | Order API base URL |

For UAT: `ORDER_BASE_URL=https://uat-order.strakertranslations.com`

## Order API Endpoints

### GET /languages?type=ecfmg

Returns available ECFMG language options. Response is cached for 1 hour.

### GET /countries

Returns available countries. Response is cached for 1 hour.

### POST /file/save

Uploads a document. Multipart form with fields:
- `file` -- the document
- `token` -- session UUID (ties to the job)
- `fileUUID` -- per-file UUID

### POST /job

Creates an ECFMG job. Form-urlencoded with fields:
- `firstname`, `lastname`, `email`, `phone` -- personal details
- `sl`, `tl` -- source/target language codes
- `country` -- country numeric ID
- `session` -- session UUID (matches file upload token)
- `certtype`, `jobtype` -- fixed as `ECFMG`
- `category`, `subcategory`, `categoryvalue` -- fixed ECFMG constants
- `bPolice` -- terms acceptance (2 = accepted)
- `bAd` -- marketing opt-in (1 = yes)
- `fromurl` -- derived from ORDER_BASE_URL hostname
- `notes` -- optional notes

Response includes job ID, quote details (price, tax, total), and a `paymentLink` URL.

## Testing

Run ECFMG-specific tests:

```bash
pipenv run pytest tests/test_order_client.py tests/test_ecfmg.py -v
```
