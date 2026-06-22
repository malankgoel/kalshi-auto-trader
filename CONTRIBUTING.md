# Contributing

## Local setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e ".[dev]"
make check
```

Keep exchange-wide behavior in `kalshi_auto_trader/kalshi`, `orders.py`, or
`ledger.py`. Strategy-specific models, market mappings, and data paths belong
under `kalshi_auto_trader/<strategy>/`.

Never commit API keys, private key files, or populated trade ledgers. New order
and risk behavior should include an offline regression test.
