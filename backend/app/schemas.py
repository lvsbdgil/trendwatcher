from pydantic import BaseModel, ConfigDict, Field, model_validator


class Article(BaseModel):
    id: int | str | None = None
    title: str = ""
    source: str = "Unknown"
    url: str = ""
    date: str = ""
    snippet: str = ""
    full_text: str = ""
    markdown: str = ""
    fetched_at: str = ""


class AnalyzeRequest(BaseModel):
    articles: list[Article]
    top_n: int = Field(default=5, ge=1, le=10)
    use_llm: bool = True


class FirecrawlScrapeRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)


class FirecrawlCrawlRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)
    limit: int = Field(default=15, ge=1, le=50)


class FirecrawlSearchRequest(BaseModel):
    """Search payload.

    Backward-compatible aliases:
      - `searchQuery` → `query`
      - `resultsLimit` → `limit`
    """
    model_config = ConfigDict(extra="ignore")

    query: str = ""
    limit: int = Field(default=10, ge=1, le=30)
    lang: str = Field(default="ru")

    @model_validator(mode="before")
    @classmethod
    def _accept_aliases(cls, data):
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        if not payload.get("query"):
            payload["query"] = payload.get("searchQuery") or payload.get("q") or ""
        if "limit" not in payload or payload.get("limit") in (None, ""):
            alias = payload.get("resultsLimit") or payload.get("count")
            if alias is not None:
                payload["limit"] = alias
        return payload


