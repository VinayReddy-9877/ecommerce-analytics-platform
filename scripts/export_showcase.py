"""Execute SQL showcase queries and save the first 12 rows as real examples."""

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from olist.config import engine

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / "sql/showcase/samples"
folder.mkdir(exist_ok=True)
with engine().connect() as connection:
    for path in sorted((ROOT / "sql/showcase").glob("*.sql")):
        result = pd.read_sql(text(path.read_text()), connection)
        result.head(12).to_csv(folder / (path.stem + ".csv"), index=False)
        print(path.name, len(result))
