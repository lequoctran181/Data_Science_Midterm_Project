#!/usr/bin/env python3
import os
import re
import json
import time
import math
import hashlib
import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from tqdm import tqdm
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from textblob import TextBlob

try:
    from dateutil.relativedelta import relativedelta
except Exception:
    relativedelta = None

try:
    from deep_translator import GoogleTranslator
except Exception:
    GoogleTranslator = None


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_COMMENT_THREADS_URL = "https://www.googleapis.com/youtube/v3/commentThreads"
YOUTUBE_COMMENTS_URL = "https://www.googleapis.com/youtube/v3/comments"


@dataclass
class Window:
    start: datetime
    end: datetime


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def dt_to_rfc3339(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_yt_datetime(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def anonymize_text(text: str) -> str:
    text = re.sub(r"https?://\S+|www\.\S+", " <URL> ", text)
    text = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", " <EMAIL> ", text)
    text = re.sub(r"(?<!\w)@[A-Za-z0-9_\.]+", " <USER> ", text)
    text = re.sub(r"(?:\+?\d[\d\s\-\.]{7,}\d)", " <PHONE> ", text)
    return normalize_whitespace(text)


def stable_hash(value: str, salt: str) -> str:
    return hashlib.sha256((salt + "||" + value).encode("utf-8")).hexdigest()


def infer_topic(query: str) -> str:
    q = query.lower()
    if "lạm phát" in q or "inflation" in q or "cpi" in q:
        return "inflation"
    if "lãi suất" in q or "interest rate" in q or "rate hike" in q or "rate cut" in q:
        return "interest_rate"
    return "economic_growth"


def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default


def make_windows(start_dt: datetime, end_dt: datetime, freq: str = "year") -> List[Window]:
    windows: List[Window] = []
    if freq not in {"year", "quarter", "month"}:
        raise ValueError("freq must be one of: year, quarter, month")

    cur = start_dt
    while cur < end_dt:
        if freq == "year":
            nxt = cur.replace(year=cur.year + 1)
        elif freq == "quarter":
            if relativedelta is None:
                raise ImportError("python-dateutil is required for quarter windows")
            nxt = cur + relativedelta(months=3)
        else:
            if relativedelta is None:
                raise ImportError("python-dateutil is required for month windows")
            nxt = cur + relativedelta(months=1)
        if nxt > end_dt:
            nxt = end_dt
        windows.append(Window(start=cur, end=nxt))
        cur = nxt
    return windows


class YouTubeCollector:
    def __init__(self, api_key: str, sleep_sec: float = 0.1, timeout: int = 60):
        self.api_key = api_key
        self.sleep_sec = sleep_sec
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, url: str, params: Dict, max_retries: int = 5) -> Dict:
        params = dict(params)
        params["key"] = self.api_key
        last_err = None
        for attempt in range(max_retries):
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                if r.status_code in {500, 502, 503, 504}:
                    time.sleep((2 ** attempt) + self.sleep_sec)
                    continue
                if r.status_code == 403:
                    try:
                        payload = r.json()
                    except Exception:
                        payload = {"error": {"message": r.text}}
                    msg = json.dumps(payload, ensure_ascii=False)
                    if "quota" in msg.lower() or "commentsDisabled" in msg:
                        raise RuntimeError(msg)
                r.raise_for_status()
                time.sleep(self.sleep_sec)
                return r.json()
            except Exception as e:
                last_err = e
                time.sleep((2 ** attempt) + self.sleep_sec)
        raise RuntimeError(f"GET failed after retries: {url} | {params} | {last_err}")

    def search_videos(self, query: str, start_dt: datetime, end_dt: datetime,
                      max_pages: int = 1, per_page: int = 50,
                      relevance_language: str = "vi", region_code: str = "VN") -> List[Dict]:
        items = []
        page_token = None
        pages = 0
        while True:
            params = {
                "part": "snippet",
                "type": "video",
                "q": query,
                "maxResults": min(per_page, 50),
                "order": "relevance",
                "publishedAfter": dt_to_rfc3339(start_dt),
                "publishedBefore": dt_to_rfc3339(end_dt),
                "relevanceLanguage": relevance_language,
                "regionCode": region_code,
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get(YOUTUBE_SEARCH_URL, params)
            for it in data.get("items", []):
                vid = it.get("id", {}).get("videoId")
                sn = it.get("snippet", {})
                if not vid:
                    continue
                items.append({
                    "video_id": vid,
                    "query": query,
                    "search_published_at": sn.get("publishedAt"),
                    "video_title": sn.get("title"),
                    "video_description": sn.get("description"),
                    "channel_id": sn.get("channelId"),
                    "channel_title": sn.get("channelTitle"),
                    "window_start": dt_to_rfc3339(start_dt),
                    "window_end": dt_to_rfc3339(end_dt),
                })
            page_token = data.get("nextPageToken")
            pages += 1
            if not page_token or pages >= max_pages:
                break
        return items

    def enrich_videos(self, video_ids: List[str]) -> Dict[str, Dict]:
        out: Dict[str, Dict] = {}
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            params = {
                "part": "snippet,statistics",
                "id": ",".join(batch),
                "maxResults": 50,
            }
            data = self._get(YOUTUBE_VIDEO_URL, params)
            for it in data.get("items", []):
                vid = it.get("id")
                if not vid:
                    continue
                sn = it.get("snippet", {})
                st = it.get("statistics", {})
                out[vid] = {
                    "video_published_at": sn.get("publishedAt"),
                    "video_title_full": sn.get("title"),
                    "video_description_full": sn.get("description"),
                    "channel_id": sn.get("channelId"),
                    "channel_title": sn.get("channelTitle"),
                    "comment_count": safe_int(st.get("commentCount"), 0),
                    "view_count": safe_int(st.get("viewCount"), 0),
                }
        return out

    def fetch_comments_for_video(self, video_id: str, topic: str, query: str,
                                 start_dt: datetime, end_dt: datetime,
                                 salt: str,
                                 max_comment_pages_per_video: int = 20,
                                 fetch_replies: bool = True) -> List[Dict]:
        rows: List[Dict] = []
        page_token = None
        pages = 0
        while True:
            params = {
                "part": "snippet,replies",
                "videoId": video_id,
                "maxResults": 100,
                "textFormat": "plainText",
                "order": "time",
            }
            if page_token:
                params["pageToken"] = page_token
            try:
                data = self._get(YOUTUBE_COMMENT_THREADS_URL, params)
            except RuntimeError as e:
                msg = str(e)
                if "commentsDisabled" in msg or "videoNotFound" in msg:
                    break
                raise

            for thread in data.get("items", []):
                t_sn = thread.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                top_id = thread.get("snippet", {}).get("topLevelComment", {}).get("id")
                if top_id:
                    created = parse_yt_datetime(t_sn.get("publishedAt")) if t_sn.get("publishedAt") else None
                    if created and start_dt <= created <= end_dt:
                        author_id = t_sn.get("authorChannelId", {}).get("value") or t_sn.get("authorDisplayName", "")
                        raw = t_sn.get("textDisplay") or t_sn.get("textOriginal") or ""
                        rows.append({
                            "platform": "youtube",
                            "topic": topic,
                            "query": query,
                            "video_id": video_id,
                            "comment_id": top_id,
                            "parent_id": None,
                            "is_reply": False,
                            "published_at": created.isoformat(),
                            "like_count": safe_int(t_sn.get("likeCount"), 0),
                            "author_hash": stable_hash(author_id, salt) if author_id else None,
                            "text_raw": normalize_whitespace(raw),
                            "text_anon": anonymize_text(raw),
                        })

                inline_replies = thread.get("replies", {}).get("comments", []) or []
                for rep in inline_replies:
                    r_sn = rep.get("snippet", {})
                    rep_id = rep.get("id")
                    created = parse_yt_datetime(r_sn.get("publishedAt")) if r_sn.get("publishedAt") else None
                    if created and start_dt <= created <= end_dt:
                        author_id = r_sn.get("authorChannelId", {}).get("value") or r_sn.get("authorDisplayName", "")
                        raw = r_sn.get("textDisplay") or r_sn.get("textOriginal") or ""
                        rows.append({
                            "platform": "youtube",
                            "topic": topic,
                            "query": query,
                            "video_id": video_id,
                            "comment_id": rep_id,
                            "parent_id": top_id,
                            "is_reply": True,
                            "published_at": created.isoformat(),
                            "like_count": safe_int(r_sn.get("likeCount"), 0),
                            "author_hash": stable_hash(author_id, salt) if author_id else None,
                            "text_raw": normalize_whitespace(raw),
                            "text_anon": anonymize_text(raw),
                        })

                if fetch_replies:
                    total_replies = safe_int(thread.get("snippet", {}).get("totalReplyCount"), 0)
                    if top_id and total_replies > len(inline_replies):
                        rows.extend(self.fetch_replies(parent_id=top_id, video_id=video_id, topic=topic, query=query,
                                                       start_dt=start_dt, end_dt=end_dt, salt=salt))

            page_token = data.get("nextPageToken")
            pages += 1
            if not page_token or pages >= max_comment_pages_per_video:
                break
        return rows

    def fetch_replies(self, parent_id: str, video_id: str, topic: str, query: str,
                      start_dt: datetime, end_dt: datetime, salt: str) -> List[Dict]:
        rows: List[Dict] = []
        page_token = None
        while True:
            params = {
                "part": "snippet",
                "parentId": parent_id,
                "maxResults": 100,
                "textFormat": "plainText",
            }
            if page_token:
                params["pageToken"] = page_token
            data = self._get(YOUTUBE_COMMENTS_URL, params)
            for rep in data.get("items", []):
                r_sn = rep.get("snippet", {})
                rep_id = rep.get("id")
                created = parse_yt_datetime(r_sn.get("publishedAt")) if r_sn.get("publishedAt") else None
                if created and start_dt <= created <= end_dt:
                    author_id = r_sn.get("authorChannelId", {}).get("value") or r_sn.get("authorDisplayName", "")
                    raw = r_sn.get("textDisplay") or r_sn.get("textOriginal") or ""
                    rows.append({
                        "platform": "youtube",
                        "topic": topic,
                        "query": query,
                        "video_id": video_id,
                        "comment_id": rep_id,
                        "parent_id": parent_id,
                        "is_reply": True,
                        "published_at": created.isoformat(),
                        "like_count": safe_int(r_sn.get("likeCount"), 0),
                        "author_hash": stable_hash(author_id, salt) if author_id else None,
                        "text_raw": normalize_whitespace(raw),
                        "text_anon": anonymize_text(raw),
                    })
            page_token = data.get("nextPageToken")
            if not page_token:
                break
        return rows


def clean_dataset(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    df["published_at"] = pd.to_datetime(df["published_at"], utc=True, errors="coerce")
    df = df.dropna(subset=["published_at", "comment_id", "text_anon"])
    df["text_anon"] = df["text_anon"].astype(str).map(normalize_whitespace)
    df = df[df["text_anon"].str.len() >= 5]
    df = df.drop_duplicates(subset=["platform", "comment_id"])
    df = df.sort_values("published_at").reset_index(drop=True)
    return df


def sentiment_label(compound: float) -> str:
    if compound >= 0.05:
        return "positive"
    if compound <= -0.05:
        return "negative"
    return "neutral"


def maybe_translate(text: str, translator, cache: Dict[str, str]) -> str:
    if translator is None:
        return text
    key = text.strip()
    if not key:
        return key
    if key in cache:
        return cache[key]
    try:
        translated = translator.translate(key)
    except Exception:
        translated = key
    cache[key] = translated
    return translated


def score_sentiment(df: pd.DataFrame, engine: str = "vader", translate: bool = False) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    analyzer = SentimentIntensityAnalyzer()
    translator = GoogleTranslator(source="auto", target="en") if (translate and GoogleTranslator is not None) else None
    cache: Dict[str, str] = {}

    compounds = []
    polarities = []
    subjectivities = []
    texts_for_model = []

    iterator = tqdm(df["text_anon"].tolist(), desc="Scoring sentiment", unit="comment")
    for text in iterator:
        txt = maybe_translate(text, translator, cache) if translate else text
        texts_for_model.append(txt)
        if engine == "textblob":
            blob = TextBlob(txt)
            pol = float(blob.sentiment.polarity)
            sub = float(blob.sentiment.subjectivity)
            polarities.append(pol)
            subjectivities.append(sub)
            compounds.append(pol)
        else:
            score = analyzer.polarity_scores(txt)
            compounds.append(float(score["compound"]))
            polarities.append(float(score["compound"]))
            subjectivities.append(None)

    df["text_for_sentiment"] = texts_for_model
    df["sentiment_score"] = compounds
    df["polarity"] = polarities
    df["subjectivity"] = subjectivities
    df["sentiment_label"] = df["sentiment_score"].map(sentiment_label)
    return df


def aggregate_monthly(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    x = df.copy()
    x["month"] = x["published_at"].dt.to_period("M").astype(str)
    g = x.groupby(["month", "topic"], dropna=False)
    out = g.agg(
        n_comments=("comment_id", "count"),
        avg_sentiment=("sentiment_score", "mean"),
        positive_ratio=("sentiment_label", lambda s: (s == "positive").mean()),
        negative_ratio=("sentiment_label", lambda s: (s == "negative").mean()),
        neutral_ratio=("sentiment_label", lambda s: (s == "neutral").mean()),
        median_sentiment=("sentiment_score", "median"),
        p10_sentiment=("sentiment_score", lambda s: s.quantile(0.10)),
        p90_sentiment=("sentiment_score", lambda s: s.quantile(0.90)),
    ).reset_index()

    all_g = x.groupby(["month"], dropna=False).agg(
        n_comments=("comment_id", "count"),
        avg_sentiment=("sentiment_score", "mean"),
        positive_ratio=("sentiment_label", lambda s: (s == "positive").mean()),
        negative_ratio=("sentiment_label", lambda s: (s == "negative").mean()),
        neutral_ratio=("sentiment_label", lambda s: (s == "neutral").mean()),
        median_sentiment=("sentiment_score", "median"),
        p10_sentiment=("sentiment_score", lambda s: s.quantile(0.10)),
        p90_sentiment=("sentiment_score", lambda s: s.quantile(0.90)),
    ).reset_index()
    all_g["topic"] = "all"

    out = pd.concat([out, all_g], ignore_index=True)
    out = out.sort_values(["month", "topic"]).reset_index(drop=True)
    return out


def build_default_queries() -> List[str]:
    return [
        '"tăng trưởng kinh tế" Việt Nam',
        '"lạm phát" Việt Nam',
        '"lãi suất" Việt Nam',
        '"Vietnam economic growth"',
        '"Vietnam inflation"',
        '"Vietnam interest rate"',
        'GDP Việt Nam',
        'CPI Việt Nam',
        'ngân hàng nhà nước lãi suất',
    ]


def main():
    parser = argparse.ArgumentParser(description="Collect public YouTube comments about Vietnam macro expectations and compute sentiment.")
    parser.add_argument("--api-key", default=os.getenv("YOUTUBE_API_KEY"), help="YouTube Data API key")
    parser.add_argument("--years-back", type=int, default=10)
    parser.add_argument("--start-date", default=None, help="Override start date, e.g. 2016-01-01")
    parser.add_argument("--end-date", default=None, help="Override end date, e.g. 2026-03-18")
    parser.add_argument("--window-freq", choices=["year", "quarter", "month"], default="year")
    parser.add_argument("--max-search-pages", type=int, default=1)
    parser.add_argument("--max-videos-per-window-query", type=int, default=50)
    parser.add_argument("--max-comment-pages-per-video", type=int, default=20)
    parser.add_argument("--target-comments", type=int, default=20000)
    parser.add_argument("--engine", choices=["vader", "textblob"], default="vader")
    parser.add_argument("--translate-before-sentiment", action="store_true")
    parser.add_argument("--queries-file", default=None, help="TXT file, one query per line")
    parser.add_argument("--outdir", default="output_public_sentiment")
    parser.add_argument("--hash-salt", default=os.getenv("HASH_SALT", "replace_me_with_random_salt"))
    parser.add_argument("--region-code", default="VN")
    parser.add_argument("--relevance-language", default="vi")
    args = parser.parse_args()

    if not args.api_key:
        raise SystemExit("Missing API key. Set YOUTUBE_API_KEY or pass --api-key.")

    end_dt = parse_yt_datetime(args.end_date + "T00:00:00Z") if args.end_date else utc_now()
    if args.start_date:
        start_dt = parse_yt_datetime(args.start_date + "T00:00:00Z")
    else:
        if relativedelta is None:
            raise SystemExit("python-dateutil is required. Install requirements first.")
        start_dt = end_dt - relativedelta(years=args.years_back)

    os.makedirs(args.outdir, exist_ok=True)

    if args.queries_file:
        with open(args.queries_file, "r", encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
    else:
        queries = build_default_queries()

    collector = YouTubeCollector(api_key=args.api_key)
    windows = make_windows(start_dt, end_dt, freq=args.window_freq)

    print(f"Time range: {start_dt.isoformat()} -> {end_dt.isoformat()}")
    print(f"Windows: {len(windows)} | Queries: {len(queries)}")

    raw_video_rows = []
    for q in tqdm(queries, desc="Searching videos", unit="query"):
        for w in windows:
            rows = collector.search_videos(
                query=q,
                start_dt=w.start,
                end_dt=w.end,
                max_pages=args.max_search_pages,
                per_page=min(args.max_videos_per_window_query, 50),
                relevance_language=args.relevance_language,
                region_code=args.region_code,
            )
            raw_video_rows.extend(rows)

    videos_df = pd.DataFrame(raw_video_rows)
    if videos_df.empty:
        raise SystemExit("No videos found. Try broader queries or larger windows.")

    videos_df = videos_df.drop_duplicates(subset=["video_id"]).reset_index(drop=True)
    meta = collector.enrich_videos(videos_df["video_id"].tolist())
    meta_df = pd.DataFrame.from_dict(meta, orient="index").reset_index().rename(columns={"index": "video_id"})
    videos_df = videos_df.merge(meta_df, on="video_id", how="left", suffixes=("", "_meta"))
    videos_df["comment_count"] = videos_df["comment_count"].fillna(0).astype(int)
    videos_df["view_count"] = videos_df["view_count"].fillna(0).astype(int)
    videos_df["topic"] = videos_df["query"].map(infer_topic)

    videos_df = videos_df.sort_values(["comment_count", "view_count"], ascending=False).reset_index(drop=True)
    videos_df.to_csv(os.path.join(args.outdir, "youtube_video_index.csv"), index=False, encoding="utf-8-sig")

    rows = []
    seen_comments = set()

    for rec in tqdm(videos_df.to_dict("records"), desc="Fetching comments", unit="video"):
        topic = rec["topic"]
        query = rec["query"]
        video_id = rec["video_id"]
        try:
            batch = collector.fetch_comments_for_video(
                video_id=video_id,
                topic=topic,
                query=query,
                start_dt=start_dt,
                end_dt=end_dt,
                salt=args.hash_salt,
                max_comment_pages_per_video=args.max_comment_pages_per_video,
                fetch_replies=True,
            )
        except Exception as e:
            print(f"Skip video {video_id}: {e}")
            continue

        for x in batch:
            cid = x.get("comment_id")
            if cid and cid not in seen_comments:
                seen_comments.add(cid)
                rows.append(x)

        if len(rows) >= args.target_comments:
            break

    df = pd.DataFrame(rows)
    df = clean_dataset(df)

    if df.empty:
        raise SystemExit("No comments collected after cleaning.")

    df = score_sentiment(df, engine=args.engine, translate=args.translate_before_sentiment)
    monthly = aggregate_monthly(df)

    raw_csv = os.path.join(args.outdir, "youtube_comments_sentiment_raw.csv")
    raw_pq = os.path.join(args.outdir, "youtube_comments_sentiment_raw.parquet")
    monthly_csv = os.path.join(args.outdir, "youtube_sentiment_monthly.csv")
    summary_json = os.path.join(args.outdir, "collection_summary.json")

    df.to_csv(raw_csv, index=False, encoding="utf-8-sig")
    try:
        df.to_parquet(raw_pq, index=False)
    except Exception:
        raw_pq = None
    monthly.to_csv(monthly_csv, index=False, encoding="utf-8-sig")

    summary = {
        "start": start_dt.isoformat(),
        "end": end_dt.isoformat(),
        "queries": queries,
        "n_unique_videos": int(videos_df["video_id"].nunique()),
        "n_comments": int(len(df)),
        "sentiment_engine": args.engine,
        "translated_before_sentiment": bool(args.translate_before_sentiment),
        "outputs": {
            "video_index_csv": os.path.abspath(os.path.join(args.outdir, "youtube_video_index.csv")),
            "raw_csv": os.path.abspath(raw_csv),
            "raw_parquet": os.path.abspath(raw_pq) if raw_pq else None,
            "monthly_csv": os.path.abspath(monthly_csv),
        },
        "label_distribution": df["sentiment_label"].value_counts(dropna=False).to_dict(),
        "topic_distribution": df["topic"].value_counts(dropna=False).to_dict(),
    }
    with open(summary_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print("Done.")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()