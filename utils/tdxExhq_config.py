
# datapath = ''
datapath = 'option_data\\'

ExHQsvr = '39.108.28.120'#'183.240.166.231 '# '134.175.214.53'
ExHQsvrport = 7727

HQsvr = '119.147.212.81'#'111.230.189.225'
HQsvrport = 7709

ETF300code = '513050'
optionLongCode = '10003283'
optionShortCode = '10003292'
optionLongName = '300ETF购5000'
optionShortName = '300ETF沽5000'


# 沪深A股
url_code_hs = 'http://71.push2.eastmoney.com/api/qt/clist/get?cb=jQuery1124024569593216308738_1596880118513&pn=1&pz=20&' \
              'po=1&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fltt=2&invt=2&fid=f3&fs=m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,' \
              'm:1+t:23&fields=f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,' \
              'f62,f128,f136,f115,f152&_=1596880118514'

# headers_data = {
#     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
#                   'Chrome/80.0.3987.149 Safari/537.36',
# }

headers_code = {
    'Accept': '*/*',
    'Accept-Encoding': 'gzip,deflate',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Connection': 'keep-alive',
    'Host': 'myfavor1.eastmoney.com',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                  'Chrome/80.0.3987.149 Safari/537.36'
}

# 数据库配置
username = 'root'
password = '123456'
db_server = '127.0.0.1'
port = '3306'
dbname = 'test'

# 获取现有的股票代码
get_code_sql = """
        select stock_code from test.MASTER_STOCK_CODE
"""

# 插入code
sql_insert_code = """
        INSERT INTO test.MASTER_STOCK_CODE(stock_code, stock_name, hisvalid, createtime, updatetime)
        VALUES (%s, %s, %s, %s, %s) on duplicate key update stock_code = values(stock_code),
        stock_name = values(stock_name), HISVALID = values(HISVALID),
        UPDATETIME = values(UPDATETIME)
        """

sql_insert_info = """
        INSERT INTO test.stock_ownership(dt, stock_code, stock_name, close_price_the_day, up_or_down_the_day, hold_the_number, share_hold_price,
                           share_hold_perce_of_A, share_hold_price_one, share_hold_price_five, share_hold_price_eten, 
                           hisvalid, createtime, updatetime)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) on duplicate key update dt = values(dt),
        stock_code = values(stock_code),stock_name = values(stock_name), close_price_the_day = values(close_price_the_day),
        up_or_down_the_day = values(up_or_down_the_day),hold_the_number = values(hold_the_number), 
        share_hold_price = values(share_hold_price),share_hold_perce_of_A = values(share_hold_perce_of_A),
        share_hold_price_one = values(share_hold_price_one), share_hold_price_five = values(share_hold_price_five),
        share_hold_price_eten = values(share_hold_price_eten),HISVALID = values(HISVALID),
        UPDATETIME = values(UPDATETIME)
"""