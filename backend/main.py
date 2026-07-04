"""
main.py
=======

このファイルの役割:
  FastAPIアプリケーションの「入口」。
  サーバーを起動すると、このファイルが最初に実行される。

現時点の状態:
  まだAPIのエンドポイント(api/ 配下)を作っていないので、
  「動作確認用の最小限のルート」だけを用意している。
  今後 api/ にエンドポイントを増やしたら、ここで読み込んで登録していく。

起動方法(Docker経由):
  docker compose up

起動方法(ローカルで直接、確認用):
  cd backend
  uvicorn main:app --reload
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import get_db
from app.core.symbols_config import get_twelve_data_symbol
from app.services.twelve_data_client import fetch_time_series, TwelveDataError
from app.services.price_data_service import save_price_data, get_recent_price_data
from app.indicators.technical_indicators import add_all_indicators
from app.strategies.trend_analyzer import analyze_higher_timeframe_trend
from app.strategies.signal_generator import generate_signal
from app.services.discord_notifier import send_signal_notification
from app.services.scheduler import start_scheduler
from app.api.signals import router as signals_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPIアプリの起動時・終了時に実行される処理。

    起動時:
      バックグラウンドのスケジューラ(定期的なシグナルチェック)を開始する。
    終了時:
      スケジューラを安全に停止する。
    """
    scheduler = start_scheduler()
    app.state.scheduler = scheduler  # 後で状態確認できるよう app.state に保持
    yield
    scheduler.shutdown()


app = FastAPI(
    title="FX Signal App API",
    description="FX半自動売買シグナル支援アプリのバックエンドAPI",
    version="0.1.0",
    lifespan=lifespan,
)

# --- CORS設定 ---
# フロントエンド(Next.js, localhost:3000)からのアクセスを許可する。
# これがないと、ブラウザがセキュリティ上の理由でAPIへのアクセスをブロックする。
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+|\d+\.\d+\.\d+\.\d+):3000",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(signals_router)


@app.get("/")
def read_root():
    """
    動作確認用のルートエンドポイント。
    ブラウザで http://localhost:8000/ を開くとこれが呼ばれる。
    """
    return {
        "message": "FX Signal App API is running",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/health")
def health_check():
    """
    ヘルスチェック用エンドポイント。
    アプリが正常に動いているかを確認するために使う
    (将来、監視ツールやDockerのヘルスチェックからも呼べる)。
    """
    return {"status": "ok"}


# =========================================
# ここから動作確認用の一時的なエンドポイント
# (正式な api/ 配下の実装ができたら削除する)
# =========================================


@app.get("/debug/fetch-and-save")
async def debug_fetch_and_save(
    symbol: str = "USDJPY",
    timeframe: str = "5m",
    output_size: int = 50,
    db: Session = Depends(get_db),
):
    """
    [動作確認用] Twelve Data APIからデータを取得し、DBに保存するテスト用エンドポイント。

    使い方:
      http://localhost:8000/debug/fetch-and-save?symbol=USDJPY&timeframe=5m&output_size=250

    注意:
      これは開発中の動作確認のためだけに用意した一時的なエンドポイント。
      本番運用ではポーリング処理(将来 services/scheduler.py 等で実装)が
      自動でこの役割を担うため、最終的には削除する。

      output_size: 取得する本数。SMA200を有効にするには250本程度を推奨。
      Twelve Dataの無料プランは1分あたり8リクエストの制限があるため、
      output_sizeを増やしすぎても1回のリクエストで取得できる本数には
      上限がある(無料プランはおおむね5000本まで)。
    """
    try:
        twelve_data_symbol = get_twelve_data_symbol(symbol)
        df = await fetch_time_series(twelve_data_symbol, timeframe, output_size=output_size)
        saved_count = save_price_data(db, symbol, timeframe, df)

        return {
            "status": "ok",
            "symbol": symbol,
            "timeframe": timeframe,
            "fetched_rows": len(df),
            "newly_saved_rows": saved_count,
        }
    except TwelveDataError as e:
        return {"status": "error", "message": str(e)}
    

@app.get("/debug/recent-data")
def debug_recent_data(
    symbol: str = "USDJPY",
    timeframe: str = "5m",
    db: Session = Depends(get_db),
):
    """
    [動作確認用] DBに保存済みの価格データを確認するテスト用エンドポイント。

    使い方:
      http://localhost:8000/debug/recent-data?symbol=USDJPY&timeframe=5m
    """
    df = get_recent_price_data(db, symbol, timeframe, limit=10)
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "count": len(df),
        "data": df.to_dict(orient="records"),
    }

@app.get("/debug/indicators")
def debug_indicators(
    symbol: str = "USDJPY",
    timeframe: str = "5m",
    db: Session = Depends(get_db),
):
    """
    [動作確認用] DBの価格データから指標(SMA, RSI, MACD, ATR, BB)を計算して確認する。

    使い方:
      http://localhost:8000/debug/indicators?symbol=USDJPY&timeframe=5m

    注意:
      データ本数が指標の計算期間(例: SMA200なら200本)に満たない場合、
      その指標の値は null(NaN)になる。これは正常な挙動。
    """
    df = get_recent_price_data(db, symbol, timeframe, limit=300)
    if df.empty:
        return {"status": "error", "message": "価格データがありません。先に /debug/fetch-and-save でデータを取得してください。"}

    df_with_indicators = add_all_indicators(df)

    # 直近5本だけ返す(全部返すと見づらいため)
    recent = df_with_indicators.tail(5)

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "total_rows": len(df),
        "columns": list(df_with_indicators.columns),
        "recent_data": recent.to_dict(orient="records"),
    }

@app.get("/debug/signal")
def debug_signal(
    symbol: str = "USDJPY",
    entry_timeframe: str = "5m",
    db: Session = Depends(get_db),
):
    """
    [動作確認用] 上位足(1時間足)トレンド判定 + 下位足シグナル判定を
    一連で実行し、最終的なシグナル結果を確認する。

    使い方:
      http://localhost:8000/debug/signal?symbol=USDJPY&entry_timeframe=5m

    前提:
      事前に1時間足と、entry_timeframe(例:5m)のデータを
      /debug/fetch-and-save で取得済みであること。
      例:
        /debug/fetch-and-save?symbol=USDJPY&timeframe=1h
        /debug/fetch-and-save?symbol=USDJPY&timeframe=5m
    """
    df_1h = get_recent_price_data(db, symbol, "1h", limit=300)
    if df_1h.empty:
        return {
            "status": "error",
            "message": "1時間足のデータがありません。先に /debug/fetch-and-save?symbol=USDJPY&timeframe=1h でデータを取得してください。",
        }
    df_1h_with_indicators = add_all_indicators(df_1h)
    trend_direction = analyze_higher_timeframe_trend(df_1h_with_indicators)

    df_entry = get_recent_price_data(db, symbol, entry_timeframe, limit=300)
    if df_entry.empty:
        return {
            "status": "error",
            "message": f"{entry_timeframe}のデータがありません。先に /debug/fetch-and-save で取得してください。",
        }
    df_entry_with_indicators = add_all_indicators(df_entry)

    result = generate_signal(df_entry_with_indicators, trend_direction, symbol)

    return {
        "symbol": symbol,
        "entry_timeframe": entry_timeframe,
        "higher_tf_trend": trend_direction.value,
        "signal_type": result.signal_type,
        "score": result.score,
        "strength_label": result.strength_label,
        "entry_price": result.entry_price,
        "atr_value": result.atr_value,
        "reasons": result.reasons,
    }

@app.get("/debug/signal-and-notify")
async def debug_signal_and_notify(
    symbol: str = "USDJPY",
    entry_timeframe: str = "5m",
    db: Session = Depends(get_db),
):
    """
    [動作確認用] シグナル判定を行い、その結果をDiscordに通知する。

    使い方:
      http://localhost:8000/debug/signal-and-notify?symbol=USDJPY&entry_timeframe=5m

    前提:
      事前に1時間足と、entry_timeframe(例:5m)のデータを
      /debug/fetch-and-save で取得済みであること。
      .env の DISCORD_WEBHOOK_URL に本物のWebhook URLが設定されていること。
    """
    df_1h = get_recent_price_data(db, symbol, "1h", limit=300)
    if df_1h.empty:
        return {"status": "error", "message": "1時間足のデータがありません。"}
    df_1h_with_indicators = add_all_indicators(df_1h)
    trend_direction = analyze_higher_timeframe_trend(df_1h_with_indicators)

    df_entry = get_recent_price_data(db, symbol, entry_timeframe, limit=300)
    if df_entry.empty:
        return {"status": "error", "message": f"{entry_timeframe}のデータがありません。"}
    df_entry_with_indicators = add_all_indicators(df_entry)

    result = generate_signal(df_entry_with_indicators, trend_direction, symbol)

    notified = await send_signal_notification(symbol, result)

    return {
        "symbol": symbol,
        "signal_type": result.signal_type,
        "score": result.score,
        "strength_label": result.strength_label,
        "discord_notified": notified,
    }

@app.get("/debug/scheduler-status")
def debug_scheduler_status():
    """
    [動作確認用] バックグラウンドのスケジューラが正常に動作しているか確認する。

    使い方:
      http://localhost:8000/debug/scheduler-status
    """
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is None:
        return {"status": "error", "message": "スケジューラがapp.stateに見つかりません"}

    jobs = scheduler.get_jobs()
    return {
        "status": "ok",
        "scheduler_running": scheduler.running,
        "jobs": [
            {
                "id": job.id,
                "next_run_time": str(job.next_run_time),
            }
            for job in jobs
        ],
    }


@app.get("/debug/run-now")
async def debug_run_now(db: Session = Depends(get_db)):
    """
    [動作確認用] スケジューラの定期実行を待たずに、今すぐ全銘柄の
    「データ取得→指標計算→シグナル判定→(WEAK以上なら)Discord通知」を
    実行し、各銘柄の結果を返す。

    使い方:
      http://localhost:8000/debug/run-now

    注意:
      これは開発・確認用のショートカット。本番運用では
      scheduler.py の定期実行(デフォルト5分おき)が自動でこの処理を行う。
      5銘柄 × 2時間足(1h, 5m)のAPI呼び出しを行うため、
      Twelve Dataの無料プランのレート制限(1分8リクエスト)に注意。
    """
    from app.core.symbols_config import SYMBOLS
    from app.services.scheduler import check_signal_for_symbol_with_result, API_REQUEST_INTERVAL_SECONDS
    import asyncio

    symbol_list = list(SYMBOLS.keys())
    results = []
    for i, symbol in enumerate(symbol_list):
        result_info = await check_signal_for_symbol_with_result(symbol)
        results.append(result_info)
        if i < len(symbol_list) - 1:
            await asyncio.sleep(API_REQUEST_INTERVAL_SECONDS)

    return {"status": "ok", "results": results}