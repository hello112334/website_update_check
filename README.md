# website_update_check for AWS Lambda winth S3
## Basic files
- app.py: main program
- list.csv: url list(64 cities + 1 google website for test)
- update_list.csv: compared result of last and current website
  - True: Same
  - False: not Same

## Compare Standard
1. Html content of url
* Image file(for check)

## Description
* This tool can download HTML Script automatically from url list(list.csv).

## Getting Started
### Dependencies
* AWS Lambda with Python 3.11.

### Main packages and APIs
1. BeautifulSoup
2. requests
3. ssl
4. slack-sdk
5. openai

### 0. Download this project and go to the folder with CMD
```
cd (YOUR_PATH)/website_update_check_tool
```

### 1. Package Install
```
pip install -r requirements.txt
```

or you can just pickup packages you need

### 2. python script.py
```
python app.py
```

## Other
### Update requirements.txt
```
pip freeze > requirements.txt
```

## Refrence
### python-slack-sdk
https://slack.dev/python-slack-sdk/webhook/index.html