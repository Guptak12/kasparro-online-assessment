# Generated output

`results.json` is the schema-valid output generated from the supplied 50-resume assessment dataset
with Gemini and GitHub enrichment enabled.

Regenerate it by running:

```bash
python main.py --input /path/to/50-resumes --output output/results.json
```

Treat production `results.json` as private because it contains applicant email addresses and
resume-derived evidence.
