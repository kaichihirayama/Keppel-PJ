# J-REIT Underwriting Benchmark

[English README](README.en.md)

J-REITの有価証券報告書等から物件単位のデータを収集・正規化し、Comparable Propertiesの検索とOCC・賃料坪単価・Cap Rate等のアンダーライティング指標の比較・集計を行うアプリケーション。

現在はPhase 1（PoC）の基盤構築段階です。対象銘柄は12社（[対象銘柄](#対象銘柄)参照）を設定済みですが、実際の抽出パイプラインはまず日本ビルファンド投資法人（8951）1社で完成させてから他銘柄へ展開する方針です。

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

`.env.example` を `.env` にコピーし、APIキーを設定してください。

```bash
cp .env.example .env
```

`.env` の内容:

```
EDINET_API_KEY=your_api_key_here
DATABASE_PATH=data/jreit.db
```

- EDINET APIキーは https://api.edinet-fsa.go.jp/ で取得できます
- `.env` はGit管理対象外です（`.gitignore` 参照）。**APIキーの値をコードやREADMEに直接書き込まないこと**

（駅距離・ビルグレードの外部調査用にGemini API等の追加を検討中。導入時は別途 `GEMINI_API_KEY` 等を追記します）

## データベースの初期化

```bash
python -m src.database.database
```

`data/jreit.db` にSQLiteスキーマ（jreit_master, properties, property_metrics, source_records）を作成します。

## 対象銘柄の投入

対象銘柄は `config/poc_targets.yaml` で管理します。追加・変更後は以下でDBへ反映します（`reit_code` が既存の場合はスキップされ、再実行しても安全です）。

```bash
python -m src.database.seed
```

### 対象銘柄

| 証券コード | 銘柄名 | EDINETコード |
|---|---|---|
| 8951 | 日本ビルファンド投資法人 | E13206 |
| 8952 | ジャパンリアルエステイト投資法人 | E13205 |
| 8958 | グローバル・ワン不動産投資法人 | E13678 |
| 8975 | いちごオフィスリート投資法人 | E14150 |
| 8976 | 大和証券オフィス投資法人 | E14197 |
| 3290 | Ｏｎｅリート投資法人 | E27884 |
| 8972 | ＫＤＸ不動産投資法人 | E14109 |
| 8955 | 日本プライムリアルティ投資法人 | E13448 |
| 8966 | 平和不動産リート投資法人 | E14005 |
| 8977 | 阪急阪神リート投資法人 | E14207 |
| 3462 | 野村不動産マスターファンド投資法人 | E31931 |
| 3451 | トーセイ・リート投資法人 | E30997 |

EDINETコードはfudosandb.jpの銘柄別ページ（URLとページ内表示名の照合）で確認したもので、正式なEDINETコード一覧での再確認は未実施です。

## EDINET書類の検索・取得

```bash
python -m src.edinet.api
```

指定日にEDINETへ提出された文書一覧の件数を表示します（接続確認用）。

```bash
python -m src.edinet.documents E13206 --start 2026-02-01 --end 2026-04-30
```

指定したEDINETコードについて、日付範囲内の有価証券報告書を検索し、最新のものを `data/raw/documents/` にダウンロードします。EDINETには銘柄名から書類を直接検索するAPIがないため、日付ごとに一覧を取得して絞り込む方式です。ダウンロード済みの `docID` は再取得しません。

ファイルは `{docID}_type{N}.{zip|pdf}` の形式で保存されます（type=1: XBRL一式のzip、type=2: PDF）。

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

## データソース調査結果（重要）

日本ビルファンド投資法人の実際の開示資料を解析した結果、フィールドごとに入手元が異なることが判明しています。今後の抽出実装（`src/extraction/property_parser.py`、未実装）はこの前提で設計します。

| データ項目 | 入手元 | 備考 |
|---|---|---|
| 所在地・地積・用途地域・建物構造・延床面積・建築時期 | 有価証券報告書（EDINET） | 物件ごとの個票（縦持ちの表）に記載 |
| 取得価格・貸借対照表計上額・鑑定評価額・鑑定機関・投資比率 | 有価証券報告書（EDINET） | 物件別サマリー表に記載（地域区分でrowspanあり） |
| 稼働率・賃貸可能面積・賃貸面積・当期賃貸収入・テナント数 | 有価証券報告書（EDINET） | 別の物件別パフォーマンス表に記載。物件名称で名寄せが必要 |
| **物件別NOI** | 各REIT公式サイトのIRライブラリ（例: NBFの「物件毎データ」Excel、`個別物件の収益状況`シート） | EDINET外。銘柄ごとにファイル形式・入手方法が異なる可能性が高い |
| **Cap Rate**（鑑定NOI利回り等） | 直接開示されていない。上記NOI（年換算）÷ 取得価格 or 鑑定評価額で算出 | `extraction_method="computed"` として、計算に使った元データもsource_recordsに記録する方針 |
| 最寄駅・徒歩分数・ビルグレード | 有価証券報告書にも資産運用報告にも記載なし | 外部情報源（Gemini API等の検索併用LLM）での補完を検討中。取得できても`confidence`は低めに設定し、公式開示情報と明確に区別する |

有価証券報告書のiXBRL/PDFはタグでテキストが分断されているため、単純なキーワード検索では見落としが発生します（実際に「最寄駅」等が0件と誤判定した経緯あり）。抽出実装では必ずBeautifulSoup等でHTML構造をパースし、`<table>`要素単位で処理してください。

## ディレクトリ構成

```
├── app/                  # Streamlit UI（Phase 4で実装）
├── config/
│   └── poc_targets.yaml  # 対象銘柄リスト（12社）
├── data/
│   ├── raw/
│   │   └── documents/    # EDINET/IRサイトから取得した原本（Git管理外）
│   ├── processed/        # 加工後データ
│   └── jreit.db          # SQLite DB（Git管理外）
├── notebooks/            # 探索的分析・抽出検証用ノートブック
├── src/
│   ├── config.py         # 設定ファイルローダー
│   ├── edinet/
│   │   ├── api.py        # documents.json（提出書類一覧）の取得
│   │   └── documents.py  # 銘柄・期間指定での書類検索とダウンロード
│   ├── extraction/
│   │   └── normalizer.py # 半期→年間換算（property_parser.py は未実装）
│   ├── database/         # ORMモデル・DB接続・シード
│   └── analytics/        # Comparable検索・統計（Phase 5で実装）
└── tests/                # pytest
```

## 開発フェーズ

1. **PoC**（進行中）: 対象12銘柄を設定済み。まず日本ビルファンド投資法人1社で「EDINET取得→物件DB→検索→平均/中央値」を完成させ、他銘柄へ展開する
2. **Pipeline**: EDINET取得・抽出・正規化・検証の自動化（IRサイトのNOIデータ取得を含む）
3. **Scale**: 全J-REITへ拡張
4. **Application**: Streamlit UI、Export、Charts
5. **Advanced**: Comparable Benchmark、Cap Rate Sensitivity、外部API（Gemini等）による属性補完

## 注意事項

本アプリケーションは投資判断を自動で確定するものではなく、公開情報を用いたComparable / Underwriting分析を支援するツールです。Cap Rate・賃料・OCC等は資料ごとに定義が異なる可能性があるため、数値だけでなく定義・出典・期間を保持しています。特にCap Rateは多くの場合、開示された数値そのものではなく算出値であることに注意してください。
