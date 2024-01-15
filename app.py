"""
website update check
work on AWS Lambda
"""
# Basic
import datetime
from slack_sdk.webhook import WebhookClient
import os
from io import StringIO
import time
import random
import pandas as pd
import ssl
import difflib
import boto3

# Scrapy
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup

# OpenAI
import openai

# .env Parameters
OUTPUT_PATH = os.environ['OUTPUT_PATH']
WEB_HOOK_URL = os.environ['WEB_HOOK_URL']
OPENAI_API_KEY = os.environ['OPENAI_API_KEY']

# S3 bucket
S3_BUCKETNAME = 'noto-support-info-news'

# ssl
class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = ssl.create_default_context()
        context.set_ciphers('DEFAULT@SECLEVEL=1')  # Lowering security level
        kwargs['ssl_context'] = context
        return super(SSLAdapter, self).init_poolmanager(*args, **kwargs)
session = requests.Session()
session.mount('https://', SSLAdapter())

class Info_news_slack:
    """
    Slack
    """

    def __init__(self):
        """note"""
        self.webhook = WebhookClient(WEB_HOOK_URL)
        self.update_list = []

    def update_status(self, text):
        """note"""
        self.update_list.append(text)

    def send(self, now_str):
        """note"""
        # md形式のテキスト
        text = ""

        # 基本情報
        text += f"[{now_str}][更新状況]\n"
        max_length = 1000  # Slack messageの最大文字数4000までに

        # 更新状況
        if len(self.update_list) > 0:
            text += "下記のサイトは更新がありました\n"
            for update_text in self.update_list:
                if len(text) + len(update_text) > max_length:
                    # 現在のメッセージを送信して新しいメッセージを開始
                    self.send_message(text)
                    text = ""  # テキストをリセット

                text += update_text + "\n"

            # 残りのテキストを送信
            if text:
                self.send_message(text)
        else:
            text += "更新なし\n"
            self.send_message(text)

    def send_message(self, text):
        """Slackにメッセージを送信する"""

        try:
            print(f"[INFO] Slack Send {'-'*30}")
            print(f"[INFO] {text}")
            response = self.webhook.send(
                text="fallback",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": text
                        }
                    }
                ]
            )
            
            # if response.status_code != 200:
            #     raise Exception("slackに送信することが失敗しました")
        except Exception as e:
            print(f"[ERROR] {e}")


def main():
    """note"""


def sleep_random(sec):
    """
    ランダムにスリープする
    :param sec: スリープする秒数
    """

    slp_time = random.random()*sec + 2.0
    time.sleep(slp_time)


def get_list():
    """
    リストを取得する
    """
    # リストをnpで取得
    df = pd.read_csv('list.csv', header=0, dtype=str, encoding='shift_jis')

    # リストをリスト型に変換
    list = df.values.tolist()

    return list


def init(i, city, town):
    """
    初期化
    :param i: インデックス
    :param city: 市区町村
    :param town: 市区町村
    :param bucket: S3バケット

    フォルダを作成する
    """
    print(f"[INFO][{i}] INIT")

    # create folder in S3
    create_folder_on_s3(f"{city}/{town}/")

def extract_html_diff(old_html, new_html):
    """
    2つのHTML間の差分を抽出します。
    :param old_html: 古いHTMLの内容
    :param new_html: 新しいHTMLの内容
    :return: 差分の内容
    """
    old_soup = BeautifulSoup(old_html, 'html.parser', from_encoding='shift_jis')
    new_soup = BeautifulSoup(new_html, 'html.parser', from_encoding='shift_jis')

    # HTMLを整形して文字列に変換
    old_text = old_soup.prettify()
    new_text = new_soup.prettify()

    # 差分を取得
    diff = difflib.ndiff(old_text.splitlines(keepends=True),
                         new_text.splitlines(keepends=True))

    # 差分の中で追加または変更された行を抽出
    diff_text = [line for line in diff if line.startswith(
        '+ ') or line.startswith('- ')]

    return '\n'.join(diff_text)


def check_update(i, city, town, text, now_str):
    """
    Updates the CSV file with new data and checks for changes from previous updates.

    Parameters:
    i (int): Index of the row to update.
    city, town (str): Parameters used in the get_txt function.
    text (str): The current text data to compare.
    now_str (str): The current update timestamp.

    Returns:
    status (bool): True if the data has changed since the last update, False otherwise.
    summary (str): The summary of the changes between the current and previous data.

    None: The function updates the CSV file in place.
    """
    # Read the CSV file from S3
    update_list_path = f"update_list.csv"
    data = read_file_on_s3(update_list_path)
    data = data.strip()

    # Switch data into a DataFrame
    df = pd.read_csv(StringIO(data), sep=',', header=0, dtype=str)

    # Add the current update timestamp as a new column if it doesn't exist
    if now_str not in df.columns:
        print(f"[INFO][{i}] Add Column : {now_str}")
        df[now_str] = ""

    # Update only if last_update is not NaN and current data is different from last data
    update_status = False
    summary = ""
    if not pd.isna(df.at[i, 'last_update']):
        if now_str != df.at[i, 'last_update']:
            # Retrieve the last update timestamp
            last_update = df.at[i, 'last_update']
            print(f"[INFO][{i}] Last Update : {last_update}")

            # Retrieve data from last update
            # last_data = get_txt(city, town, last_update)
            last_data = read_file_on_s3(f"{city}/{town}/{last_update}.txt")

            # Compare with current data
            check_result = last_data == text
            
            if not check_result:
                try:
                    diff = extract_html_diff(last_data, text)
                    print(f"[INFO][{i}] Diff : {diff}")
                    summary = gpt_summarize(diff)
                except Exception as err:
                    print(f"[ERROR][{i}] {err}")
                    summary = "要約失敗"

            # Update the comparison result in the dataframe
            df.at[i, now_str] = check_result
            df.at[i, 'last_update'] = now_str

            # 更新結果
            if not check_result:
                update_status = True
    else:
        # If last_update is NaN, mark as "-"
        df.at[i, now_str] = "-"
        df.at[i, 'last_update'] = now_str

    # Save the updated DataFrame back to CSV on S3
    save_file_on_s3(update_list_path, df.to_csv(index=False))

    return update_status, summary

def read_file_on_s3(file_name):
    """
    S3上のファイルを読み込む
    :param file_name: ファイル名
    :return: ファイルの中身
    """
    print(f"[INFO] Read File: {file_name}")
    s3 = boto3.client('s3')
    response = s3.get_object(Bucket=S3_BUCKETNAME, Key=file_name)
    body = response['Body'].read()

    return body.decode('utf-8')

def save_file_on_s3(file_name, data):
    """
    S3上にファイルを保存する
    :param file_name: ファイル名
    :param data: ファイルの中身
    """
    print(f"[INFO] Save File: {file_name}")
    s3 = boto3.resource('s3')
    s3.Bucket(S3_BUCKETNAME).put_object(Key=file_name, Body=data)

def create_folder_on_s3(folder_name):
    """
    S3上にフォルダを作成する
    :param folder_name: フォルダ名
    """
    print(f"[INFO] Create Folder: {folder_name}")
    s3 = boto3.resource('s3')
    s3.Bucket(S3_BUCKETNAME).put_object(Key=folder_name)

def gpt_summarize(text):
    """
    GPT-3を使用してテキストを要約します。
    :param text: 要約するテキスト
    :param api_key: OpenAI APIキー

    :return: 要約されたテキスト
    """
    openai.api_key = OPENAI_API_KEY
    
    # print(f"[INFO] GPT-3 Summarize: {text}")
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "あなたはジャーナリズムのスペシャリストです。"},
            {"role": "assistant", "content": f"{text}"},
            {"role": "user", "content": "この内容を日本語で要約してください。#ルール 1.要約後の文字数は50文字以内に収めること 2.文章の主要なポイントを見逃さないよう注意すること 3.内容が分からなければ「内容が分からない」で回答してください。 #補足 +:追加した情報。-:削除した情報"}],
        max_tokens=150
    )
    
    if response['choices'][0]['message']['content']:
        return response['choices'][0]['message']['content']
    else:
        return "要約できませんでした"

def lambda_handler(event, context):

    try:
        # 開始
        print(f"[INFO] START {'-'*10}")
        t_delta = datetime.timedelta(hours=9)
        JST = datetime.timezone(t_delta, 'JST')
        now = datetime.datetime.now(JST)
        now_str = str(now.strftime('%Y%m%d%H'))
        now_str2 = str(now.strftime('%Y年%m月%d日%H時'))

        # Slack init
        info_news_slack = Info_news_slack()

        # Listを取得する
        datalist = get_list()
        print("[INFO] ALL URL: {0}".format(len(datalist)))

        # リスト３列目の値(URL)を順番に取得する
        for i in range(len(datalist)):

            try:
                city_name = datalist[i][0]
                town_name = datalist[i][1]
                print(f"[INFO][{i}] {city_name} {town_name}")

                # 初期化
                init(i, city_name, town_name)

                # URLの値を取得
                get_url = datalist[i][2]
                print(f"[INFO][{i}] URL : {get_url}")

                # ブラウザのHTMLを取得
                html = session.get(get_url)

                # HTMLをBeautifulSoupで扱う
                soup = BeautifulSoup(
                    html.content, features="html.parser", from_encoding='utf-8')
                encoded_soup = soup.encode('utf-8')
                decoded_soup = encoded_soup.decode('utf-8')

                # HTMLをS3に保存
                save_file_on_s3(f"{city_name}/{town_name}/{now_str}.txt", decoded_soup)

                # 更新チェック
                print(f"[INFO][{i}] 更新チェック")
                update_status, summary = check_update(
                    i, city_name, town_name, decoded_soup, now_str)
                if update_status:
                    # print(f"[INFO] {summary}")
                    info_news_slack.update_status(
                        f"[{i+1}] {city_name} {town_name} {get_url}\n```{summary}```")

                print(f"[INFO][{i}] {'-'*10}")
            except Exception as err:
                print("[ERROR] {0}".format(err))

    except Exception as err:
        print("[ERROR] {0}".format(err))

    finally:
        # 結果をSlackに送信
        info_news_slack.send(now_str2)

        print(f"[INFO] END {'-'*10}")
