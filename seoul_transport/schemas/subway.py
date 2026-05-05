from typing import Optional
from pydantic import BaseModel



# Silver 
class SubwaySilver(BaseModel):
    
    use_ymd: str
    line_num: str
    subway_sta_nm: str
    ride_num: Optional[int]
    alight_num: Optional[int]


# 일별 승하차량 (Gold) 
class DailyUsage(BaseModel):
    
    line_num: str
    subway_sta_nm: str
    avg_ride: float
    avg_alight: float
    max_ride: float
    max_alight: float
    data_days: int          # 집계에 사용된 날짜 수

# 요일별 승하차량
class WeeklyUsage(BaseModel):
    
    line_num: str
    subway_sta_nm: str
    day_of_week: int        # 1=일, 2=월, ..., 7=토
    is_weekend: bool
    avg_ride: float
    avg_alight: float

# 월별 승하차량
class MonthlyUsage(BaseModel):
    
    line_num: str
    subway_sta_nm: str
    year_month: str         # YYYY-MM
    total_ride: int
    total_alight: int


# 환승역 (Gold) 
class TransferStation(BaseModel):
    
    subway_sta_nm: str
    line_count: int


# 환승역 이용패턴
class TransferPattern(BaseModel):
    
    subway_sta_nm: str
    line_num: str
    avg_ride: float
    avg_alight: float
    total_ride: int
    total_alight: int
