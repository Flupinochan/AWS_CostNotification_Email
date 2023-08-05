# AWSのコスト通知をEmailまたはLINEにする(o^∇^o)

## 前提
- AWSマルチアカウント (Organizations) 環境を利用している
- Budgets の filters を使用し、Linked Account を設定している  
  [AWS Budgets Document](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-create-filters.html#:~:text=.-,Linked%20Account,-Choose%20an%20AWS)
- `CostNotificationEmail.py` を使用する場合は、AWS SNS の設定がしてあること
- `CostNotificationLINE.py` を使用する場合は、LINE Notify Tokenが発行してあること  
  [LINE Notify](https://notify-bot.line.me/my/)

## 利用方法

### 1. AWS Lambda 設定
   1. #### コード 設定
      ファイル名とハンドラ設定を忘れずに設定してください。
      - `LoggingClass.py`
      - `CostNotificationEmail.py` ※AWS SNS を使用し、コストをメールに通知する場合に必要
      - `CostNotificationLINE.py` ※コストを LINE に通知する場合に必要

   2. #### 環境変数 設定
      次の環境変数を設定します。
      - `ACCOUNT_ID` : Organizations Master Account
      - `BUDGET_NAME` : Budget で作成した予算の名前
      - `LOG_LEVEL` : `INFO` または `DEBUG`
      - `SNS_TOPIC_ARN` : SNSトピック ARN ※`CostNotificationEmail.py`を使用する場合に必要
      - `LINE_NOTIFY_TOKEN` : LINE (PC) で発行したトークン ※`CostNotificationLINE.py`を使用する場合に必要

   3. #### IAMロール 設定
      下記、AWSリソースへのアクセス権限が必要です。
      - `CloudWatch Logs`
      - `Organizations`
      - `Cost Explorer`
      - `Budgets`
      - `SNS`

### 2. AWS EventBridge ルール設定
   AWS EventBridge のルールにて、Cron設定を行います。毎月末に通知を行いたい場合は、以下の設定を行います。
   ```bash
   0 0 L * ? *