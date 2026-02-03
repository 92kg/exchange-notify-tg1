"""
辅助工具函数
"""

def format_price(price: float, decimals: int = 2) -> str:
    """
    格式化价格
    :param price: 价格
    :param decimals: 小数位数
    :return: 格式化后的字符串
    """
    if price is None:
        return "N/A"
    
    if price >= 1000:
        return f"${price:,.{decimals}f}"
    else:
        return f"${price:.{decimals}f}"

def format_percentage(value: float, decimals: int = 2) -> str:
    """
    格式化百分比
    :param value: 数值
    :param decimals: 小数位数
    :return: 格式化后的字符串
    """
    if value is None:
        return "N/A"
    
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.{decimals}f}%"