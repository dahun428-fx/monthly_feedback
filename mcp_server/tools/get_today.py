import datetime

DESCRIPTION = "- get_today(args): 오늘 날짜 또는 월을 반환. 형식은 YYYY-MM-DD"

def run(args=None):
    """
    Args:
        unit (str): 'date' (기본값) 또는 'month'
    Returns:
        dict: {"today": "..."} 또는 {"month": "..."}
    """
    today = datetime.date.today()

    return {
        "today": today.strftime("%Y-%m-%d")
    }
