# Sofreight Cargo Tracking

Query or subscribe Sofreight cargo tracking by B/L or booking number.

## Install

```bash
cd skills/sofreight-cargo-tracking
pip install -r requirements.txt
```

## Configure API Key

Target env var: **`SOF_API_KEY`**. Do **not** write the key into the skill folder.

- Platform Secret / executor: inject `SOF_API_KEY` directly.
- User pastes a key in chat: run `--save` (sets process env + persists outside the skill package).

```bash
python scripts/tracking.py --status
python scripts/tracking.py --save "<KEY>"
python scripts/tracking.py --clear
```

Create a key at https://www.sofreight.com/personal_center/api_key (do not call `MemberApiKey/create` from this skill).

## Usage

```bash
python scripts/tracking.py --numbers "BL1,BL2" --confirmed                 # query
python scripts/tracking.py --numbers "BL1" --carrier COSU --confirmed     # pick carrier
python scripts/tracking.py --numbers "BL1,BL2" --subscribe --confirmed    # subscribe
python scripts/tracking.py --list                            # subscription list
python scripts/tracking.py --list --keywords "OOCL" --carrier CMA
python scripts/tracking.py --export-only                      # Excel from cache
```

Flow: validate key → identify numbers → match carrier → check quota → confirm → query/subscribe → return brief.
