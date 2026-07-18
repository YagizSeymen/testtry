# Canonical API Fixtures

Each JSON file is a direct response body for the endpoint named by the file.
The frontend can import these files without an additional wrapper. All people,
companies, signals, and evidence in this directory are synthetic.

The aggregate application fixtures are lifecycle snapshots, not simultaneous
responses:

1. `get_application_claims_only.json` — extraction complete; later stages null
2. `get_application_memo_ready.json` — Version A; memo ready, adversary null
3. `get_application_full.json` — adversary complete and human gate approved

`post_application_memo.json` intentionally contains only memo fields.
`post_application_adversary.json` contains the adversarial result and the
deterministic Decision Brief.

`post_thesis.json` is the successful write response. `get_thesis.json` is the
stored single-fund thesis returned to the client.

The founder fixture has six de-duplicated signals, one normalized source, and
one signal in the snapshot's last 30 days. The frozen formulas therefore yield
Founder Score 59 and band 22.
