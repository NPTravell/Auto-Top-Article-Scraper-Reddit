import os
import praw
from datetime import datetime
import pandas as pd
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json

subreddits = json.loads(os.getenv('SUBREDDITS'))


def reddit_scrape():
    # Reddit API credentials
    reddit = praw.Reddit(
        client_id=os.getenv('REDDIT_CLIENT_ID'),
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),
        user_agent='my-scraper',
        read_only=True
    )
    
    subreddit_threads = []
    for subreddit_name in subreddits:
        subreddit = reddit.subreddit(subreddit_name) #check each subreddit and...

        for submission in subreddit.top("month", limit=30): #grab the 30 best articles (consider increasing)
            upload_time = datetime.utcfromtimestamp(submission.created_utc)
            hours_since_upload = round((datetime.utcnow() - upload_time).total_seconds() / 3600, 1)
            
            thread = {
                'subreddit': subreddit_name,
                'title': submission.title,
                'comments': submission.num_comments,
                'likes': submission.score,
                'upload_time': upload_time.strftime('%Y-%m-%d'),
                'hours_since_post': hours_since_upload,  
                'likes_h': round(submission.score / hours_since_upload, 1),
                'comments_ph': round(submission.num_comments / hours_since_upload, 1),
                'link': submission.url
            }
            
            subreddit_threads.append(thread)

    # Convert to PD df (mostly for debugging - if it gets too big try duckdb) and send it
    df = pd.DataFrame(subreddit_threads)
    df_filtered = df[~df['link'].str.contains(r'reddit\.com|i\.redd\.it|v\.redd\.it')] #get rid of internal links (images/cross-posting)
    send_to_google_sheets(df_filtered, os.getenv('SPREADSHEETID'))



def send_to_google_sheets(data, sheet_id):
    try:
        # Setup the Sheets API
        credentials_json = os.getenv('GOOGLE_CREDENTIALS')
        credentials = json.loads(credentials_json)
        creds = Credentials.from_service_account_info(credentials)
        #creds = Credentials.from_service_account_file("credentials.json")
        creds = creds.with_scopes(["https://www.googleapis.com/auth/spreadsheets"])
        service = build("sheets", "v4", credentials=creds)
        sheet = service.spreadsheets()
        
        values = [data.columns.tolist()] + data.values.tolist()
        body = {
            'values': values
        }

        result = sheet.values().append(
            spreadsheetId=sheet_id,
            range='Sheet1!A1',
            valueInputOption='RAW',
            body=body
        ).execute()

    except HttpError as err:
        print(f"An error occurred: {err}")
