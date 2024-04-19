import json, os,re,datetime
import warnings
import time, requests
import pandas as pd
import configparser

from pytdx.hq import TdxHq_API
from pytdx.exhq import TdxExHq_API
import utils.tdxExhq_config as conf

from flask import Flask
import schedule,threading

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(1)

def update_data():
    global data
    data = drawAllCCBmin1A()
    print(data)

app = Flask(__name__)
data = {}

@app.route('/')
def hello():
    return 'Hello, this is a simple Flask web application!'

@app.route('/data')
def get_data():
    global data
    return data

warnings.filterwarnings('ignore')

def TestConnection(Api, type, ip, port):
    if type == 'HQ':
        try:
            is_connect = Api.connect(ip, port)
        except Exception as e:
            print('Failed to connect to HQ!')
            exit(0)

        if is_connect is False:
            print('HQ is_connect is False!')
            return False
        else:
            print('HQ is connected!')
            return True

    elif type=='ExHQ':
        try:
            is_connect = Api.connect(ip, port)
        except Exception as e:
            print('Failed to connect to Ext HQ!')
            exit(0)

        if is_connect is False:
            print('ExHQ is_connect is False!')
            return False
        else:
            print('ExHQ is connected')
            return True

class tdxData(object):

    def __init__(self, api, Exapi,code, backset, klines, period):

        self.code = code
        self.backset = backset
        self.klines = klines
        self.period = period
        self.api = api
        self.Exapi = Exapi

    def cal_right_price(self, input_stock_data, type='前复权'):

        stock_data = input_stock_data.copy()
        num = {'后复权': 0, '前复权': -1}

        price1 = stock_data['close'].iloc[num[type]]
        stock_data['复权价_temp'] = (stock_data['change'] + 1.0).cumprod()
        price2 = stock_data['复权价_temp'].iloc[num[type]]
        stock_data['复权价'] = stock_data['复权价_temp'] * (price1 / price2)
        stock_data.pop('复权价_temp')

        # 计算开盘复权价
        stock_data['复权价_开盘'] = stock_data['复权价'] / (stock_data['close'] / stock_data['open'])
        stock_data['复权价_最高'] = stock_data['复权价'] / (stock_data['close'] / stock_data['high'])
        stock_data['复权价_最低'] = stock_data['复权价'] / (stock_data['close'] / stock_data['low'])

        return stock_data[['复权价_开盘', '复权价', '复权价_最高', '复权价_最低']]

    def get_xdxr_EM(self,code):
        if len(code)!=5:
            return pd.DataFrame()
        url = 'https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_HKF10_MAIN_DIVBASIC'+ \
              '&columns=SECURITY_CODE,UPDATE_DATE,REPORT_TYPE,EX_DIVIDEND_DATE,DIVIDEND_DATE,TRANSFER_END_DATE,YEAR,PLAN_EXPLAIN,IS_BFP'+ \
              '&quoteColumns=&filter=(SECURITY_CODE="'+code+'")(IS_BFP="0")&pageNumber=1&pageSize=3&sortTypes=-1,-1'+ \
              '&sortColumns=NOTICE_DATE,EX_DIVIDEND_DATE&source=F10&client=PC&v=043409724372028'
        try:
            res = requests.get(url)
            data1 = pd.DataFrame(json.loads(res.text)['result']['data'])
            if len(data1)==0:
                return pd.DataFrame()
            else:
                data1.rename(columns={'EX_DIVIDEND_DATE':'date','SECURITY_CODE':'code','REPORT_TYPE':'type','PLAN_EXPLAIN':'deal'}, inplace=True)
                data1 = data1[data1['type'].str.contains('分配')]
                data1['date'] = data1['date'].apply(lambda x: x.replace('/','-'))
                data1['deal'] = data1['deal'].apply(lambda x: float(re.findall(r'\d+\.\d+(?=[^.\d]*$)',x)[-1]))
                return data1
        except:
            return pd.DataFrame()

    def fuquan(self, code, backset, qty, period):

        # fuquan = True
        zhishu = False

        if '#' in code:
            mkt = int(code.split('#')[0])
            code = code.split('#')[1]
            if mkt in [0,1,2] and len(code)!=6: # 深交所0 上交所1 北交所2
                print(code, 'unknown code')
                return pd.DataFrame()

        elif len(code)==6 and code[0] in '0123456789':  # A股
            if code[:2] in ['15','00','30','16','12','39','18']: # 深市
                mkt = 0 # 深交所
            elif code[:2] in ['51','58','56','60','68','50','88','11','99']:
                mkt = 1 # 上交所
            elif code[:2] in ['43','83','87']:
                mkt = 2 # 北交所
            else:
                print(code, 'unknown code')
                return pd.DataFrame()

        elif code[:2].lower()=='zz':    # 中证指数
            code = code[-6:]
            mkt=62

        elif code[:2].lower()=='zs':
            zhishu = True
            code = code[-6:]
            if code[:2] in ['39']: # 深市
                mkt = 0 # 深交所
            elif code[:2] in ['00']:
                mkt = 1 # 上交所
            elif code[:2] in ['43','83','87']:
                mkt = 2 # 北交所
            else:
                print(code, 'unknown code')
                return pd.DataFrame()

        elif len(code) == 5 and code[0]=='U':    # 期权指标
            mkt = 68

        elif len(code) == 5 and code[0]=='0':    # 港股通
            mkt = 71

        else:
            print(code, 'unknown code')
            return pd.DataFrame()

        if mkt not in [0,1,2]:

            if qty>600:
                df_k = pd.DataFrame()
                for i in range(qty//600):
                    temp = pd.DataFrame(self.Exapi.get_instrument_bars(period, mkt, code, 600*i+backset, 600))
                    df_k = pd.concat([temp,df_k ])
                temp = pd.DataFrame(self.Exapi.get_instrument_bars(period, mkt, code, 600*(qty//600)+backset, qty%600))
                df_k = pd.concat([temp, df_k])
            else:
                df_k = pd.DataFrame(self.Exapi.get_instrument_bars(period, mkt, code, 0+backset, qty))
            return df_k
        else:
            if qty>600:
                df_k = pd.DataFrame()
                if code[:2] in ['88','99','39'] or zhishu==True:
                    for i in range(qty//600):
                        temp = pd.DataFrame(self.api.get_index_bars(period, mkt, code, 600*i+backset, 600))
                        df_k = pd.concat([temp,df_k ])
                    temp = pd.DataFrame(self.api.get_index_bars(period, mkt, code, 600*(qty//600)+backset, qty%600))
                    df_k = pd.concat([temp, df_k])
                    return df_k # 指数不复权 直接返回数据
                else:
                    for i in range(qty//600):
                        temp = pd.DataFrame(self.api.get_security_bars(period, mkt, code, 600*i+backset, 600))
                        df_k = pd.concat([temp, df_k])
                    temp = pd.DataFrame(self.api.get_security_bars(period, mkt, code, 600*(qty//600)+backset, qty%600))
                    df_k = pd.concat([temp, df_k])
                    return df_k
            else:
                if code[:2] in ['88','99','39'] or zhishu==True:
                    df_k = pd.DataFrame(self.api.get_index_bars(period, mkt, code, 0+backset, qty))
                    return df_k # 指数不复权 直接返回数据
                else:
                    df_k = pd.DataFrame(self.api.get_security_bars(period, mkt, code, 0+backset, qty))
                    return df_k

    @property
    def get_data(self):
        df=self.fuquan(self.code, self.backset, self.klines, self.period)
        return df

def getOptionsTformat(df_4T):

    field_map3 = {'f14':'Cname','f12':'Ccode','f2':'Cprice', 'f3':'CpctChg','f4':'C涨跌额','f108':'C持仓量','f5':'Cvol','f249':'Civ','f250':'C折溢价率','f161':'行权价',
                  'f340':'Pname','f339':'Pcode','f341':'Pprice','f343':'PpctChg','f342':'P涨跌额','f345':'P持仓量','f344':'Pvol','f346':'Piv','f347':'P折溢价率'}

    df_T_data = pd.DataFrame()
    for etfcode, expiredate in zip(df_4T['ETFcode'],df_4T['到期日']):
        code= '1.'+etfcode if etfcode[0]=='5' else '0.'+etfcode

        url3 = 'https://push2.eastmoney.com/api/qt/slist/get?cb=jQuery112400098284603835751_1695513185234&'+ \
               'secid='+code+'&exti='+expiredate[:6]+ \
               '&spt=9&fltt=2&invt=2&np=1&ut=bd1d9ddb04089700cf9c27f6f7426281&fields=f1,f2,f3,f4,f5,f12,f13,f14,f108,f152,f161,'+ \
               'f249,f250,f330,f334,f339,f340,f341,f342,f343,f344,f345,f346,f347&fid=f161&pn=1&pz=20&po=0&wbp2u=|0|0|0|web&_=1695513185258'
        res = requests.get(url3)
        tmp = re.search(r'^\w+\((.*)\);$', res.text).group(1).replace('"-"','"0"')
        single = pd.DataFrame(json.loads(tmp)['data']['diff'])
        df_T_data = pd.concat([df_T_data,single])
    df_T_data.rename(columns = field_map3,inplace=True)
    df_T_data = df_T_data[list(field_map3.values())]

    return df_T_data

def getOptionsRiskData():

    field_map4 =  {"f2": "最新价","f3": "涨跌幅","f12": "code","f14": "name", "f301": "到期日",
                   "f302": "杠杆比率","f303": "实际杠杆","f325": "Delta","f326": "Gamma","f327": "Vega","f328": "Theta","f329": "Rho"}

    df_risk = pd.DataFrame()
    for i in range(1,11,1):
        url4 = 'https://push2.eastmoney.com/api/qt/clist/get?cb=jQuery112308418460865815227_1695516975860&fid=f3&po=1&'+ \
               'pz='+'50'+'&pn='+str(i)+'&np=1&fltt=2&invt=2&ut=b2884a393a59ad64002292a3e90d46a5'+ \
               '&fields=f1,f2,f3,f12,f13,f14,f302,f303,f325,f326,f327,f329,f328,f301,f152,f154&fs=m:10'
        res = requests.get(url4)
        tmp = re.search(r'^\w+\((.*)\);$', res.text).group(1).replace('"-"','"0"')
        if len(tmp)<100:
            continue
        single = pd.DataFrame(json.loads(tmp)['data']['diff'])
        df_risk = pd.concat([df_risk,single])

    df_risk.rename(columns = field_map4,inplace=True)
    df_risk = df_risk[list(field_map4.values())]

    return df_risk

def getAllOptionsV3():

    header = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/112.0',
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Cookie": "qgqp_b_id=435b18200eebe2cbb5bdd3b3af2db1b1; intellpositionL=522px; intellpositionT=1399.22px; em_hq_fls=js; pgv_pvi=6852699136; st_pvi=73734391542044; st_sp=2020-07-27%2010%3A10%3A43; st_inirUrl=http%3A%2F%2Fdata.eastmoney.com%2Fhsgt%2Findex.html",
        "Host": "push2.eastmoney.com",
    }

    field_map0 = {'f12':'code', 'f14':'name','f301':'到期日','f331':'ETFcode', 'f333':'ETFname',
                  'f2':'close','f3':'pctChg','f334':'ETFprice','f335':'ETFpct','f337':'平衡价',
                  'f250':'溢价率','f161':'行权价'}#,'f47':'vol','f48':'amount','f133':'allvol'}

    url1 = 'https://push2.eastmoney.com/api/qt/clist/get?cb=jQuery112307429657982724098_1687701611430&fid=f250'+ \
           '&po=1&pz=1000&pn=1&np=1&fltt=2&invt=2&ut=b2884a393a59ad64002292a3e90d46a5'+ \
           '&fields=f1,f2,f3,f12,f13,f14,f161,f250,f330,f331,f332,f333,f334,f335,f337,f301,f152&fs=m:10'
    res = requests.get(url1, headers=header)
    tmp = re.search(r'^\w+\((.*)\);$', res.text).group(1).replace('"-"','"0"')
    data1 = pd.DataFrame(json.loads(tmp)['data']['diff'])
    data1.rename(columns = field_map0,inplace=True)


    url2 = url1[:-1] + '2'
    res = requests.get(url2,headers=header)
    tmp = re.search(r'^\w+\((.*)\);$', res.text).group(1).replace('"-"','"0"')
    data2 = pd.DataFrame(json.loads(tmp)['data']['diff'])
    data2.rename(columns = field_map0,inplace=True)

    data = pd.concat([data1, data2])
    data = data[list(field_map0.values())]

    data['market'] = data['ETFcode'].apply(lambda x: '沪市' if x[0]=='5' else '深市')
    data['direction'] = data['name'].apply(lambda x: 'call' if '购' in x else 'put')
    data['due_date'] = data['到期日'].apply(lambda x: datetime.datetime.strptime(str(x),'%Y%m%d').date())
    data['dte'] = data['due_date'].apply(lambda x: (x-datetime.datetime.now().date()).days)
    data['close'] = data['close'].astype(float)
    data['到期日'] = data['到期日'].astype(str)
    data['行权pct'] = data.apply(lambda x:round(x['行权价']/x['ETFprice']*100-100,2),axis=1)

    df_4T = data.pivot_table(index=['ETFcode','到期日'],values=['name'],aggfunc=['count']).reset_index()
    df_4T.columns = ['ETFcode','到期日','数量']


    ######################## T-型报价
    df_T_format = getOptionsTformat(df_4T)
    tempc = df_T_format[['Ccode','C持仓量','Cvol']]
    tempc.columns = ['code','持仓量','vol']
    tempp = df_T_format[['Pcode','P持仓量','Pvol']]
    tempp.columns = ['code','持仓量','vol']
    temp = pd.concat([tempc, tempp])
    temp['vol'] = temp['vol'].astype(int)
    data = pd.merge(data, temp, on='code',how='left')
    data['amount'] = data['close']*data['vol']

    df_risk = getOptionsRiskData()

    data = pd.merge(data, df_risk[['code','杠杆比率','实际杠杆', 'Delta','Gamma','Vega','Theta','Rho']], on='code',how='left')

    return data

def getMyOptions():
    global dte_high, dte_low,close_Threshold,etfcode_dict,opt_fn

    now = pd.DataFrame(api.get_index_bars(8, 1, '999999', 0, 20))

    current_datetime = datetime.datetime.strptime(now['datetime'].values[-1],'%Y-%m-%d %H:%M')

    if os.path.exists(opt_fn):
        modified_timestamp = os.path.getmtime(opt_fn)
        modified_datetime = datetime.datetime.fromtimestamp(modified_timestamp)
        time_delta = current_datetime - modified_datetime
        gap_seconds = time_delta.days*24*3600 + time_delta.seconds
        if gap_seconds < 1000:
            print('\nreusing option file', opt_fn)
            data = pd.read_csv(opt_fn, encoding='gbk',dtype={'ETFcode':str,'code':str})
        else:
            try:
                data = getAllOptionsV3()
                print('\nNew option file', opt_fn)
                data.to_csv(opt_fn, encoding='gbk', index=False, float_format='%.4f')
            except:
                print('\nupdate failed, reusing option file', opt_fn)
                data = pd.read_csv(opt_fn, encoding='gbk', dtype={'ETFcode': str, 'code': str})
    else:
        print('\nNew option file', opt_fn)
        data = getAllOptionsV3()
        data.to_csv(opt_fn,encoding='gbk',index=False, float_format='%.4f')

    data.fillna(0,inplace=True)
    amtlist = data['amount'].values.tolist()
    amtlist.sort()
    amtthreshold = amtlist[-180]

    data = data[data['amount']>amtthreshold]
    data.sort_values(by='amount',ascending=False,inplace=True)
    data['itm'] = data.apply(lambda x: max(0,x.ETFprice-x['行权价']) if x.direction=='call' else max(0,x['行权价']-x.ETFprice),axis=1)
    data['otm'] = data.apply(lambda x: x.close-x.itm,axis=1)

    png_dict = {}
    for key in etf_dict.keys():
        etfcode = etfcode_dict[key]
        call = data[(data['ETFcode']==etfcode) & (data['direction']=='call') & (data['dte']>dte_low) & (data['dte']<dte_high) & (data['close']>close_Threshold)][:1]
        put = data[(data['ETFcode']==etfcode) & (data['direction']=='put') & (data['dte']>dte_low) & (data['dte']<dte_high) & (data['close']>close_Threshold)][:1]
        if len(call) == 0:
            tmpstr = '认购:50000000_流动性过滤为空_0.0'
        else:
            tmpstr = '认购:' + call['code'].values[0] + '_' + call['name'].values[0] + '_' + str(
                call['close'].values[0]) + ' =itm' + str(int(call['itm'].values[0]*10000)) + '+' + str(int(call['otm'].values[0]*10000)) + \
                ' 杠杆:'+str(int(call['实际杠杆'].values[0]))
        if len(put) == 0:
            tmpstr += '\n认沽:50000000_流动性过滤为空_0.0'
        else:
            tmpstr += '\n认沽:' + put['code'].values[0] + '_' + put['name'].values[0] + '_' + str(
                put['close'].values[0]) + ' =itm' + str(int(put['itm'].values[0]*10000)) + '+' + str(int(put['otm'].values[0]*10000)) + \
                ' 杠杆:'+str(int(put['实际杠杆'].values[0]))

        png_dict[key] = tmpstr


    return png_dict


def getSingleCCBData(name, period, backset, klines):
    global api, Exapi

    code = etf_dict[name]
    df_single= tdxData(api, Exapi,code,backset,klines,period).get_data
    df_single.reset_index(drop=True,inplace=True)
    if len(df_single)==0:
        print('#### ',code,'kline error !!!!')
        return pd.DataFrame()
    df_single['datetime'] = df_single['datetime'].apply(lambda x: x.replace('13:00','11:30') if x[-5:]=='13:00' else x)

    ccbcode = etf_ccb_dict[name]
    df_ccb = tdxData(api, Exapi, ccbcode,backset,klines,period).get_data
    if len(df_ccb)==0:
        print(ccbcode,'ccb error, quitting')
        return pd.DataFrame()

    df_ccb.rename(columns={'close':'ccb','high':'ccbh','low':'ccbl','open':'ccbo'},inplace=True)
    data = pd.merge(df_ccb[['datetime','ccb','ccbh','ccbl','ccbo']], df_single[['datetime','open','close','high','low']], on='datetime',how='right')

    return data

def drawAllCCBmin1A():
    global backset, threshold_pct,bins,trade_rate,trendKline, cutloss, cutprofit, png_dict

    result =  {}

    periodkey = '1分钟k线'
    period = int(kline_dict[periodkey])
    klines=int(kline_qty[periodkey])

    for k,v in etf_dict.items():
        df_single = getSingleCCBData(k,period,backset, klines)
        if len(df_single) == 0:
            continue
        df_single.sort_values(by=['datetime'],ascending=True, inplace=True)
        df_single.reset_index(drop=True, inplace=True)
        # df_single['time'] = df_single['datetime'].apply(lambda x: x.split(' ')[1])
        df_single['pctChg'] = df_single['close']/df_single['close'].shift(1)-1

        df_single['close'] = df_single['close'].ffill()
        df_single['cm5'] = df_single['close'].rolling(5).mean()
        df_single['cm20'] = df_single['close'].rolling(20).mean()
        df_single['cmgap'] = (df_single['cm5'] - df_single['cm20'])/df_single['cm5']

        df_single['gap'] = (df_single['close'] - df_single['cm20'])/df_single['close']*100
        df_single['gapabs'] = df_single['gap'].apply(lambda x: abs(x))
        gap_threshold = float(etf_threshold[k])
        df_single.loc[(df_single['gap']>gap_threshold),'gapSig'] = df_single['gap']
        df_single.loc[(df_single['gap']<-1*gap_threshold),'gapSig'] = df_single['gap']

        df_single['chhv60'] = df_single['high'].rolling(60).max()
        df_single['cllv60'] = df_single['low'].rolling(60).min()
        df_single['ccp60'] = df_single.apply(lambda x: (x['close']-x['cllv60'])/(x['chhv60']-x['cllv60']), axis=1)

        df_single['ccbm5'] = df_single['ccb'].rolling(5).mean()
        df_single['ccbm20'] = df_single['ccb'].rolling(20).mean()
        df_single['ccbmgap'] = (df_single['ccbm5'] - df_single['ccbm20'])/df_single['ccbm5']

        df_single.loc[df_single['cmgap']<0,'cmark'] = -1
        df_single.loc[df_single['cmgap']>0,'cmark'] = 1
        df_single.loc[df_single['ccbmgap']<0,'ccbmark'] = 1
        df_single.loc[df_single['ccbmgap']>0,'ccbmark'] = -1
        df_single['mark'] = df_single['ccbmark'] + df_single['cmark']

        df_single['ccbhhv60'] = df_single['ccbh'].rolling(60).max()
        df_single['ccbllv60'] = df_single['ccbl'].rolling(60).min()
        df_single['ccbcp60'] = df_single.apply(lambda x: (x['ccb']-x['ccbllv60'])/(x['ccbhhv60']-x['ccbllv60']), axis=1)
        df_single['ccbgap'] = df_single['ccp60']-df_single['ccbcp60']
        # df_single['ccbgap'] = df_single['cmgap']-df_single['ccbmgap']
        df_single['ccbgapm20'] = df_single['ccbgap'].rolling(20).mean()
        df_single.loc[(df_single['ccbgap']>df_single['ccbgapm20']) & (df_single['mark']>=0),'up2'] = 0  # (df_single['mark']>=0) &
        df_single.loc[(df_single['ccbgap']<df_single['ccbgapm20']) & (df_single['mark']<=0),'dw2'] = 0

        df_single.loc[(df_single['ccbgap']>df_single['ccbgapm20']) & (df_single['ccbgap'].shift(1)<df_single['ccbgapm20'].shift(1)),'sig'] = 1  # (df_single['mark']>=0) &
        df_single.loc[(df_single['ccbgap']<df_single['ccbgapm20']) & (df_single['ccbgap'].shift(1)>df_single['ccbgapm20'].shift(1)),'sig'] = -1

        if df_single['sig'].values[-1] == 1:    # etf上涨信号
            print('#### ',k,'上涨信号')
            calloptioncode = png_dict[k].split('\n')[0].split('_')[0][3:]
            calloptionname = png_dict[k].split('\n')[0].split('_')[1]
            if '购' not in calloptionname:
                print('error call option', calloptioncode, calloptionname)
                result[k] = {'Trx':'+C','direction': 1, 'code': 'wrong', 'name': 'wrong'}
            else:
                result[k] = {'Trx':'+C','direction':1, 'code':calloptioncode,'name':calloptionname}
        elif df_single['sig'].values[-1] == -1:  # etf下跌信号
            print('#### ', k, '下跌信号')
            putoptioncode = png_dict[k].split('\n')[1].split('_')[0][3:]
            putoptionname = png_dict[k].split('\n')[1].split('_')[1]
            if '沽' not in putoptionname:
                print('error call option', putoptioncode, putoptionname)
                result[k] = {'Trx':'+P','direction': -1, 'code': 'wrong','name':'wrong'}
            else:
                result[k] = {'Trx':'+P','direction': -1, 'code': putoptioncode,'name':putoptionname}
        else:
            if df_single['up2'].values[-1] == 0:
                calloptioncode = png_dict[k].split('\n')[0].split('_')[0][3:]
                calloptionname = png_dict[k].split('\n')[0].split('_')[1]
                if '购' not in calloptionname:
                    print('error call option', calloptioncode, calloptionname)
                    result[k] = {'Trx':'','direction': 1, 'code': 'wrong', 'name': 'wrong'}
                else:
                    result[k] = {'Trx':'','direction': 1, 'code': calloptioncode, 'name': calloptionname}
            elif df_single['dw2'].values[-1] == 0:
                putoptioncode = png_dict[k].split('\n')[1].split('_')[0][3:]
                putoptionname = png_dict[k].split('\n')[1].split('_')[1]
                if '沽' not in putoptionname:
                    print('error call option', putoptioncode, putoptionname)
                    result[k] = {'Trx':'','direction': -1, 'code': 'wrong', 'name': 'wrong'}
                else:
                    result[k] = {'Trx':'','direction': -1, 'code': putoptioncode, 'name': putoptionname}
            else:
                result[k] = {'Trx':'', 'direction': 0, 'code': 'NoTrend', 'name': 'NoTrend'}

    data = {}
    data['time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    data['data'] = result

    return data

def update_opt_list():
    global png_dict
    # try:
    png_dict_new = getMyOptions()
    update = True
    for k,v in png_dict_new.items():
        if '流动性' in v:
            update = False
            print('option list NOT updated')
            break
    if update:
        print('option list updated')
        png_dict  = png_dict_new
        print('option list:', png_dict)
    # except:
    #     print('option list logic failed')

if __name__ == '__main__':

    prog_start = time.time()
    print('-------------------------------------------')
    print('Job start !!! ' + datetime.datetime.now().strftime('%Y%m%d_%H:%M:%S'))

    cfg_fn = 'monitor2web.cfg'
    config = configparser.ConfigParser()
    config.read(cfg_fn, encoding='utf-8')
    dte_low = int(dict(config.items('option_screen'))['dte_low'])
    dte_high = int(dict(config.items('option_screen'))['dte_high'])
    close_Threshold = float(dict(config.items('option_screen'))['close_threshold'])
    etf_ccb_dict = dict(config.items('etf_ccb_dict'))
    etfcode_dict = dict(config.items('etfcode_dict'))
    etf_dict = dict(config.items('etf_dict'))
    kline_dict = dict(config.items('kline_dict'))
    kline_qty = dict(config.items('kline_qty'))
    backset = int(dict(config.items('backset'))['backset'])
    png_dict = dict(config.items('png_dict'))
    etf_threshold = dict(config.items('etf_threshold'))
    opt_path = dict(config.items('path'))['opt_path']
    output_path = dict(config.items('path'))['output_path']


    api = TdxHq_API(heartbeat=True)
    if TestConnection(api, 'HQ', conf.HQsvr, conf.HQsvrport) == False: # or \
        print('connection to TDX server not available')

    Exapi = TdxExHq_API(heartbeat=True)
    if TestConnection(Exapi, 'ExHQ', conf.ExHQsvr, conf.ExHQsvrport )==False:
        print('connection to EXHQ server not available')

    now = pd.DataFrame(api.get_index_bars(8, 1, '999999', 0, 20))
    opt_fn =  opt_path +  '\\沪深期权清单_'+ now['datetime'].values[-1][:10].replace('-','')+'.csv'

    update_opt_list()
    update_data()

    schedule.every(10).seconds.do(update_data)
    schedule.every(10).minutes.do(update_opt_list)

    schedule_thread = threading.Thread(target=run_schedule)
    schedule_thread.daemon = True
    schedule_thread.start()

    app.run()

    api.close()
    Exapi.close()

    time_end = time.time()
    print('-------------------------------------------')
    print(f'Job completed!!!  All time costed: {(time_end - prog_start):.0f}秒')
