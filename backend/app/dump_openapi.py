"""輸出 OpenAPI 規格，給前端產生 TypeScript 型別：npm run gen:api"""

import json
import sys

from app.main import app

if __name__ == "__main__":
    with open(sys.argv[1], "w", encoding="utf-8") as file:
        json.dump(app.openapi(), file, ensure_ascii=False, indent=1)
