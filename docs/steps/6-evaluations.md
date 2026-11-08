# Step 6: Review evaluations

`eval/dataset.json` contains 30 original, compact PR-diff fixtures: 20 labeled
bug cases across SQL injection, off-by-one errors, missing authorization
checks, and hardcoded secrets, plus 10 clean cases. The fake-secret marker is
synthetic, not a credential. These fixtures are a reproducible starter set,
not a substitute for a user-consented benchmark built from real repositories.

Provide model findings in a JSON file:

```json
{
  "predictions": [
    {
      "case_id": "sql-01",
      "file": "src/db.py",
      "line": 4,
      "category": "sql-injection"
    }
  ]
}
```

Score them and record or update a prompt-version row:

```powershell
shipguard eval `
  --dataset .\eval\dataset.json `
  --results .\review-results.json `
  --prompt-version prompt-v1 `
  --scores .\eval\scores.csv
```

A hit requires the expected file, a line within the dataset tolerance, and the
correct category. The report includes precision, recall, and false positives
per clean case; `eval/scores.csv` stores one row per prompt version.
