# Extractor

## Output Schema Note

The internal extractor JSON must include a required top-level `founder_name`
string alongside `claims`. Return the person's name stated in the deck; never
substitute the company name. The backend uses this value to resolve or create
the persistent founder record. This internal field does not change the public
`POST /api/applications` response, which already returns `founder_id`.
