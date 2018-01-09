#-*- coding:utf-8 -*-
'''
流量预测
'''
from test_stationarity import *
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.arima_model import ARIMA
from datetime import timedelta
import os
os.chdir(os.getcwd()+'/data')


class ModelDecomp(object):
	def __init__(self, file, test_size=180):
		self.ts = self.read_data(file)
		plt.plot(self.ts)
		plt.show()
		self.test_size = test_size
		self.train_size = len(self.ts) - self.test_size
		self.train = self.ts[:len(self.ts)-test_size]
		self.test = self.ts[-test_size:]

	def read_data(self, f):
		data = pd.read_csv(f)
		data = data.set_index('date')
		data.index = pd.to_datetime(data.index)
		ts = data['count']
		ts = self._diff_smooth(ts)
		return ts

	def _diff_smooth(self, ts):
		dif = ts.diff().dropna()
		td = dif.describe()
		high = td['75%'] + 1.5 * (td['75%'] - td['25%'])
		low = td['25%'] - 1.5 * (td['75%'] - td['25%'])

		forbid_index = dif[(dif > high) | (dif < low)].index
		for i in range(len(forbid_index) - 1):
			start = forbid_index[i]
			end = forbid_index[i + 1]
			tsvalue = ts[start:end]
			n = len(tsvalue)
			if n > 3:
				continue
			else:
				try:
					value = np.linspace(ts[start - timedelta(minutes=1)], ts[end + timedelta(minutes=1)], n)
					ts[start: end] = value
				except:
					continue
		return ts

	def decomp(self, freq):
		'''
		对时间序列进行分解
		:param freq: 周期
		'''
		decomposition = seasonal_decompose(self.ts, freq=freq, two_sided=False)
		self.trend = decomposition.trend
		self.seasonal = decomposition.seasonal
		self.residual = decomposition.resid
		decomposition.plot()
		plt.show()

		d = self.residual.describe()
		delta = d['75%'] - d['25%']

		multi_num = 1.5
		self.low_error, self.high_error = (d['25%'] - multi_num * delta, d['75%'] + multi_num * delta)

	def trend_model(self, order):
		'''
		为分解出来的趋势数据单独建模
		:return:
		'''
		self.trend.dropna(inplace=True)
		train = self.trend[:len(self.trend)-self.test_size]
		self.trend_model = ARIMA(train, order).fit(disp=-1, method='css')

		return self.trend_model

	def add_season(self):
		'''
		为预测出的趋势数据添加周期数据和残差数据
		:return:
		'''
		self.train_season = self.seasonal[:self.train_size]
		values = []
		low_conf_values = []
		high_conf_values = []

		for i, t in enumerate(self.pred_time_index):
			trend_part = self.trend_pred[i]

			# 相同时间的数据均值
			season_part = self.train_season[
				self.train_season.index.time == t.time()
				].mean()

			# 趋势+周期+误差界限
			predict = trend_part + season_part
			low_bound = trend_part + season_part + self.low_error
			high_bound = trend_part + season_part + self.high_error

			values.append(predict)
			low_conf_values.append(low_bound)
			high_conf_values.append(high_bound)

		self.final_pred = pd.Series(values, index=self.pred_time_index, name='predict')
		self.low_conf = pd.Series(low_conf_values, index=self.pred_time_index, name='low_conf')
		self.high_conf = pd.Series(high_conf_values, index=self.pred_time_index, name='high_conf')

	def predict_new(self):
		'''
		预测新数据
		'''
		#续接train，生成长度为n的时间索引，赋给预测序列
		n = self.test_size
		self.pred_time_index= pd.date_range(start=self.train.index[-1], periods=n+1, freq='1min')[1:]
		self.trend_pred= self.trend_model.forecast(n)[0]

		self.add_season()


def evaluate(filename):
	md = ModelDecomp(file=filename, test_size=1440)
	md.decomp(freq=1440)
	md.trend_model(order=(1, 1, 3))
	md.predict_new()
	pred = md.final_pred
	test = md.test

	plt.subplot(211)
	plt.plot(md.ts)
	plt.title(filename.split('.')[0])
	plt.subplot(212)
	pred.plot(color='blue', label='Predict')
	test.plot(color='red', label='Original')
	md.low_conf.plot(color='grey', label='low')
	md.high_conf.plot(color='grey', label='high')

	plt.legend(loc='best')
	plt.title('RMSE: %.4f' % np.sqrt(sum((pred.values - test.values) ** 2) / test.size))
	plt.tight_layout()
	plt.show()


if __name__ == '__main__':
	filename = 'api_access.csv'
	evaluate(filename)