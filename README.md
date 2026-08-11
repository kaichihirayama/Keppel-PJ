# J-REIT Underwriting Benchmark

J-REITの有価証券報告書等から物件単位のデータを収集・正規化し、Comparable Propertiesの検索とOCC・賃料坪単価・Cap Rate等のアンダーライティング指標の比較・集計を行うアプリケーション。

現在はPhase 1（PoC: 5銘柄程度、オフィス中心）の基盤構築段階です。

## セットアップ

### 1. 仮想環境

```bash
python -m venv venv
```

Windows:
```bash
venv\Scripts\activate
```

### 2. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 3. 環境変数の設定

`.env.example` を `.env` にコピーし、EDINET APIキーを設定してください。

```bash
cp .env.example .env
```

`.env` の内容:

```
EDINET_API_KEY=your_api_key_here
DATABASE_PATH=data/jreit.db
```

EDINET APIキーは https://api.edinet-fsa.go.jp/ で取得できます。`.env` はGit管理対象外です（`.gitignore` 参照）。

## データベースの初期化

```bash
python -m src.database.database
```

`data/jreit.db` にSQLiteスキーマ（jreit_master, properties, property_metrics, source_records）を作成します。

## PoC対象銘柄の投入

対象銘柄は `config/poc_targets.yaml` で管理します。追加・変更後は以下でDBへ反映します（`reit_code` が既存の場合はスキップされ、再実行しても安全です）。

```bash
python -m src.database.seed
```

## EDINET API接続確認

```bash
python -m src.edinet.api
```

指定日にEDINETへ提出された文書一覧の件数を表示します（APIキー未設定の場合はエラーになります）。

## テストの実行

```bash
pytest
```

## データモデル概要

- `jreit_master` — J-REITマスター（銘柄、スポンサー、EDINETコード等）
- `properties` — 物件属性（用途、所在地、最寄駅、駅距離、築年数等）
- `property_metrics` — 期別の運営・財務指標（OCC、賃料坪単価、NOI、Cap Rate各種）
- `source_records` — フィールド単位の出典・抽出方法・信頼度・検証状況を追跡する監査証跡

Cap Rateは `acquisition_cap_rate` / `appraisal_cap_rate` / `noi_yield` を独立した列として保持し、混同しないよう設計しています。OCCは0〜100%の範囲チェックを行い、原資料の定義文言が標準定義と異なる場合は `occupancy_rate_definition` に保存します。

### 半期・通期の年間換算

J-REITは半期（6ヶ月）ごとに開示する銘柄と、通期（12ヶ月）でまとめて開示する銘柄が混在しています。物件間比較の前に、`src/extraction/normalizer.py` の `annualize_metrics()` で1年分の数値へ揃えます。

- 直近が通期（`period_type="annual"`）の場合はその数値をそのまま使用
- 直近が半期（`period_type="semi_annual"`）で、連続する2期（6ヶ月差）が揃っている場合は合算
  - **NOI**（期間中に発生する金額）→ 2期を**合計**
  - **occupancy_rate / rent_per_tsubo / 各Cap Rate**（時点の比率・単価）→ 2期の**平均**
- 片方の期に値がない項目は、推測で埋めずに `None`（`missing_fields` に記録）とする
- 連続する2期が揃わない場合は年間換算せず `None` を返す（推測しない）

この判定に使う `period_type` / `period_end_date` は `property_metrics` テーブルに保持しています。

## ディレクトリ構成

```
├── app/                  # Streamlit UI（Phase 4で実装）
├── config/
│   └── poc_targets.yaml  # PoC対象銘柄リスト
├── data/
│   ├── raw/              # 取得した原本（documents/, pdf/）
│   ├── processed/        # 加工後データ
│   └── jreit.db          # SQLite DB（Git管理外）
├── notebooks/            # 探索的分析・抽出検証用ノートブック
├── src/
│   ├── config.py         # 設定ファイルローダー
│   ├── edinet/           # EDINET API連携
│   ├── extraction/       # PDF/XBRL抽出（Phase 2で実装）
│   ├── database/         # ORMモデル・DB接続・シード
│   └── analytics/        # Comparable検索・統計（Phase 5で実装）
└── tests/                # pytest
```

## 開発フェーズ

1. **PoC**（進行中）: 5銘柄程度、Office中心。物件DB→検索→平均/中央値まで
2. **Pipeline**: EDINET取得・抽出・正規化・検証の自動化
3. **Scale**: 全J-REITへ拡張
4. **Application**: Streamlit UI、Export、Charts
5. **Advanced**: Comparable Benchmark、Cap Rate Sensitivity等

## 注意事項

本アプリケーションは投資判断を自動で確定するものではなく、公開情報を用いたComparable / Underwriting分析を支援するツールです。Cap Rate・賃料・OCC等は資料ごとに定義が異なる可能性があるため、数値だけでなく定義・出典・期間を保持しています。
