# Canopy MacroPad — 実装ハンドオフ

Claude Code 向け。Phase 1（USB 有線版）の完成が当面のゴール。

---

## 1. 何を作るか

Canopy（macOS の Claude Code クライアント）の**タブ状態を物理キーの LED 色で表示し、キーを押すとそのタブに切り替わる**外部デバイスと、その macOS 側統合。

### 中核となる価値

Claude Code を複数タブで並列に回しているとき、「どのタブが自分の返事待ちか」を**画面を見ずに手元で把握できる**こと。承認待ちのタブが手元でオレンジに点滅する。押せばそこに飛ぶ。

### 絶対に守る設計原則

**デバイスを HID キーボードにしない。** `usb_hid.disable()` で USB シリアル（CDC）専用デバイスにする。理由:

- Canopy 以外のアプリにキーストロークが漏れない。エディタに文字が入る事故がゼロ
- Canopy 非起動時は押しても完全に無反応
- macOS の「入力監視（Input Monitoring）」TCC 権限が不要。IOHIDManager 経由だと権限ダイアログが出て、署名配布アプリとして印象が悪い
- シリアルポートは単なる `/dev/cu.*` へのファイル I/O。Hardened Runtime / Notarization / Gatekeeper のいずれにも抵触しない。entitlement 追加も不要
- 押下の生イベントが取れる（OS のキーリピート処理が挟まらない）

**制約**: App Sandbox 環境ではシリアルポートを開けない。Canopy は Node.js サブプロセスを spawn している時点で非サンドボックス確定なので問題なし。この前提が崩れたら設計を見直すこと。

---

## 2. ハードウェア構成（Phase 1）

| 品 | 型番 / SKU | 役割 |
|---|---|---|
| Adafruit QT Py RP2040 | ssci 7211 / ADA-4900 | コントローラ。CircuitPython |
| Adafruit NeoKey 1x4 QT | ssci 10048 / ADA-4980 | 4キー + キーごと NeoPixel |
| Qwiic ケーブル 50mm | ssci 6896 / SFE-PRT-17260 | QT Py ↔ NeoKey |
| Durock Ice King Linear | 遊舎工房 | MX 互換、クリアハウジング + LED 透過レンズ |
| 透明 ABS キーキャップ | Amazon（R4 プロファイル） | 暫定。後で 3D プリントに置換予定 |

接続は STEMMA QT / Qwiic 一本のみ。はんだ付け不要。

**NeoKey の I2C アドレスはデフォルト `0x30`。** 2枚目を足す場合のみ、基板裏の A0 ジャンパをはんだで閉じて `0x31` にする。

Phase 1 は 4 キー。最終的には 6 キーを想定しているので、**キー数をハードコードせず定数化しておくこと**。

---

## 3. ファームウェア（CircuitPython）

### 必要ライブラリ

Adafruit CircuitPython Bundle から `lib/` にコピー:

- `adafruit_neokey/`
- `adafruit_seesaw/`

`adafruit_hid` は**不要**（HID を使わないため）。

### boot.py

```python
import usb_hid
import usb_cdc
import supervisor

# HID キーボードとして名乗らない。これが設計の中核。
usb_hid.disable()

# console: デバッグ用 REPL / data: アプリ通信用
usb_cdc.enable(console=True, data=True)

supervisor.set_usb_identification(
    manufacturer="Whatever",
    product="Canopy MacroPad",
)
```

**注意**: `boot.py` の変更は物理的な USB 抜き差しで反映される。リセットボタンだけでは反映されないことがある。

### code.py

```python
import board
import usb_cdc
from adafruit_neokey.neokey1x4 import NeoKey1x4

NUM_PADS = 1                      # NeoKey 基板の枚数
ADDRESSES = [0x30, 0x31][:NUM_PADS]
NUM_KEYS = 4 * NUM_PADS

i2c = board.STEMMA_I2C()
pads = [NeoKey1x4(i2c, addr=a) for a in ADDRESSES]
for p in pads:
    p.pixels.brightness = 0.3     # フル輝度は眩しすぎる。実測で調整

serial = usb_cdc.data
prev = [False] * NUM_KEYS
buf = b""


def set_color(idx, rgb):
    if 0 <= idx < NUM_KEYS:
        pads[idx // 4].pixels[idx % 4] = rgb


def handle(line):
    parts = line.decode().strip().split()
    if not parts:
        return
    cmd = parts[0]
    if cmd == "C" and len(parts) == 3:          # C <idx> <rrggbb>
        set_color(int(parts[1]), int(parts[2], 16))
    elif cmd == "B" and len(parts) == 2:        # B <0-100> 明るさ
        b = max(0, min(100, int(parts[1]))) / 100
        for p in pads:
            p.pixels.brightness = b
    elif cmd == "P":                            # P ping
        serial.write(b"PONG\n")
    elif cmd == "R":                            # R reset 全消灯
        for i in range(NUM_KEYS):
            set_color(i, 0x000000)


while True:
    # --- ホストからのコマンド受信（非ブロッキング）---
    if serial.in_waiting:
        buf += serial.read(serial.in_waiting)
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            try:
                handle(line)
            except Exception as e:
                serial.write(f"ERR {e}\n".encode())

    # --- キー読み取り（エッジ検出）---
    for i in range(NUM_KEYS):
        now = pads[i // 4][i % 4]
        if now != prev[i]:
            serial.write(f"K {i} {1 if now else 0}\n".encode())
            prev[i] = now
```

### プロトコル仕様

行区切り ASCII。人間がシリアルモニタで直接叩けることを優先。

**ホスト → デバイス**

| コマンド | 意味 |
|---|---|
| `C <idx> <rrggbb>` | キー idx の色を設定。例: `C 0 ff8000` |
| `B <0-100>` | 全体の明るさ |
| `P` | ping。`PONG` が返る |
| `R` | 全消灯 |

**デバイス → ホスト**

| メッセージ | 意味 |
|---|---|
| `K <idx> <0\|1>` | キー idx の押下(1) / 離し(0) |
| `PONG` | ping 応答 |
| `ERR <msg>` | コマンド処理エラー |

将来 BLE に移行しても、この行プロトコルをそのまま GATT の characteristic に載せられるよう、**プロトコル層と物理層を分離して実装すること**。

---

## 4. macOS 側実装

### 4.1 新規ファイル

```
Canopy/
  MacroPad/
    MacroPadDevice.swift      # シリアル接続・再接続・送受信
    MacroPadProtocol.swift    # コマンド/イベントのエンコード・デコード
    MacroPadController.swift  # AppState 購読 → 色決定 → 送信 / キー押下 → タブ操作
    MacroPadStatus.swift      # タブ状態 → 色 のマッピング定義
```

**先に既存コードを調査すること。** 以下は既知の手がかりだが、正確な型名・API は実際のリポジトリで確認する:

- `ShimProcess.swift` — Node.js サブプロセスと NDJSON で双方向通信。SSE イベントがここを経由して WKWebView に流れている
- `StatusBarView.swift` — コンテキスト使用量・モデル・レートリミットを扱っている。状態集約のフック候補
- タブ管理は Cmd+T / Cmd+1〜9 のショートカットで既に存在する

理想は既存のイベントストリームを分岐させるだけで済む形:

```
Node subprocess ──NDJSON──> ShimProcess ──┬──> WKWebView
                                          └──> MacroPadController ──> MacroPadDevice
```

### 4.2 シリアルポートの発見

**デバイスパスをハードコードしない。** `/dev/cu.usbmodem1101` の番号はポートやリブートで変わる。

`IOServiceMatching("IOSerialBSDClient")` で列挙し、以下のいずれかでマッチさせる:

- 親 USB デバイスの VID/PID
- `boot.py` の `set_usb_identification` で設定した product name（`"Canopy MacroPad"`）

**ホットプラグ対応**: `IOServiceAddMatchingNotification` で接続/切断を監視し、自動再接続する。デバイスが存在しなくても Canopy は通常起動すること。ケーブルが抜けていても一切支障がない設計にする。

ライブラリは `ORSSerialPort` を使うか、POSIX termios で直接書く。依存を増やしたくないなら後者で十分（`open` / `read` / `write` + `cfsetspeed`）。CDC-ACM ではボーレート設定は実質無視されるので、任意の値でよい。

### 4.3 状態 → 色マッピング

`MacroPadStatus.swift` に集約し、後から調整しやすくする。

| タブ状態 | 色 | 挙動 |
|---|---|---|
| 空きスロット（タブなし） | 消灯 | — |
| アイドル | 暗いグレー 0x101010 | 常時点灯 |
| 実行中（thinking / tool use） | 青 0x0040ff | 常時点灯 |
| **承認待ち / 入力待ち** | オレンジ 0xff8000 | **点滅（1Hz）** |
| 完了（未読） | 緑 0x00ff40 | 常時点灯 |
| エラー | 赤 0xff0000 | 常時点灯 |

**設計上のルール:**

- **明るさを状態の区別に使わない。** 周辺光の影響で明るさの差は読み取れない。色相だけで区別する
- **点滅は「承認待ち」1種類だけ。** 2つ以上を点滅させると意味が薄れ、周辺視野での気づきやすさが失われる
- 点滅はデバイス側ではなくホスト側のタイマーで実装してよい（1Hz なら通信量は無視できる）。ただし将来 BLE 化する際はデバイス側に移す前提で、`MacroPadDevice` の背後に隠すこと

### 4.4 キー押下の扱い

- `K <idx> 1` → タブ idx へ切り替え
- キー数 < タブ数のケースを考慮する。マッピングは「先頭 N タブ」固定でよいが、ハードコードせず `MacroPadController` に隔離
- 長押し・同時押しは Phase 1 では実装しない。ただし `K` イベントは押下と離しの両方を送っているので、後から追加できる形にしておく

### 4.5 設定

以下は設定可能にしておく（UserDefaults で十分）:

- 有効 / 無効トグル
- 全体輝度（0-100）
- 色マッピングのカスタマイズ（Phase 2 でよい）

---

## 5. 動作確認手順

1. QT Py に CircuitPython の UF2 を書き込む
2. `lib/` に `adafruit_neokey` と `adafruit_seesaw` をコピー
3. `boot.py` を配置し、**USB を物理的に抜き差し**
4. `ls /dev/cu.*` で 2 本の usbmodem が見えることを確認（console と data）
5. `code.py` を配置
6. data 側のポートに `screen /dev/cu.usbmodemXXXX 115200` で接続
7. `P` と打って `PONG` が返ることを確認
8. `C 0 ff0000` でキー 0 が赤くなることを確認
9. キーを押して `K 0 1` / `K 0 0` が流れることを確認
10. **テキストエディタにフォーカスを移してキーを押し、何も入力されないことを確認**（HID 無効化の検証）

10 番目が最重要。ここが通らなければ `usb_hid.disable()` が効いていない。

---

## 6. 完了条件（Phase 1）

- [ ] Canopy 起動時にデバイスを自動検出して接続する
- [ ] デバイス未接続でも Canopy が正常に起動・動作する
- [ ] ケーブル抜き差しで自動再接続する
- [ ] タブの状態変化が 200ms 以内に LED に反映される
- [ ] 承認待ちタブが点滅する
- [ ] キー押下で該当タブに切り替わる
- [ ] Canopy 非起動時、キーを押しても他アプリに一切影響しない
- [ ] Canopy 終了時に LED を消灯する（`R` を送ってからポートを閉じる）

---

## 7. 今回スコープ外（将来の Phase）

実装時に**この方向への移行を妨げない**ようにだけ配慮する。今は作らない。

### Phase 2: 6キー化 + 筐体

- Adafruit NeoKey Snap-Apart 5x6 PCB を 1x6 または 3x2 に割って使用（基板設計不要）
- キーキャップを 3D プリント（光造形）に置換。KeyV2 または Keycap Playground をベースに、underset legend（裏面刻印）で消灯時は無地、点灯時のみタブ番号が浮かぶ形を狙う
- レジンはクリア + Tenacious 10-20% ブレンド（純クリアは脆く、MX ステムが割れる）

### Phase 3: ロープロファイル化

- Kailh Choc V2 Deep Sea Mini（MX ステム / 透明 PC ハウジング / SK6812MINI-E 前提設計）
- Choc V1 と同一フットプリント（15×15mm）なので Corne (crkbd) の KiCad プロジェクトを流用可能
- QT Py RP2040 は castellated なので子基板として親基板に直付けできる。USB 周りの自前設計を回避する

### Phase 4: ワイヤレス + MagSafe ドック

- **ボタン電池は不可。** SK6812MINI-E は消灯時も約 1mA/個 を消費し、動作電圧も 3.5V 以上。CR2032（225mAh / 3V）では成立しない
- nice!nano v2 + LiPo 200-250mAh が唯一まともな構成
- ディスプレイ下の既設 MagSafe マウントに載せる場合、磁石リング外径 56mm の制約から筐体は 65mm 角程度になり、レイアウトは 1x6 ではなく 3x2 になる
- Qi は直結せず `Qi受電 → MCP73831 → LiPo → 3.3V` とする。軽負荷だと送電側が停止するため
- ドック中は輝度を自動的に下げる（Qi の発熱対策）
- BLE 化するとホスト→LED 制御にカスタム GATT サービスの自作が必要になり、macOS 側も CoreBluetooth + `NSBluetoothAlwaysUsageDescription` の TCC プロンプトが発生する。有線版でソフトが完成してから着手すること

---

## 8. 実装順序の指示

**必ずこの順で進めること。** 並行して手を出すと切り分け不能になる。

1. ファームウェアを書き、シリアルモニタで手打ち検証（セクション 5）
2. `MacroPadProtocol` + `MacroPadDevice` を単体で実装。CLI ツールかテストで接続・送受信を確認
3. Canopy の既存状態管理を調査し、フックポイントを特定
4. `MacroPadController` で結線
5. UI（設定トグル・輝度）

3 の調査結果は実装前に共有すること。既存アーキテクチャへの理解が誤っていると、この後の設計がすべてずれる。
