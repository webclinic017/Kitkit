# coding=utf-8
from multiprocessing import Process, Queue, Pool
from multiprocessing.managers import BaseManager
import os, sys, time, random
import pymongo
from pymongo import MongoClient
import argparse
import numpy as np
from munch import Munch
import pandas as pd
from tqdm import tqdm
"""
功能
1，创建Queue
2，连接mongodb
3，提取优先级高，并且undo的特征组
4, write()到Queue
5, 暴露Queue到通信中
4, update queue timingly

"""
def delay(x, period=1):
    """
    [Definition] 序列x中前period天的价格
    [Category] 技术指标
    delay() value of x d days ago
    """
    res = np.zeros(x.shape) * np.nan
    res[period:] = x[:-period]
    return res


class QueueManager(BaseManager):
    pass


class TaskQueue():
    def __init__(self, queue_size, db_host, db_port, db_name, db_collection):
        self.config = Munch()
        self.config.db_host = db_host
        self.config.db_port = db_port
        self.config.db_name = db_name
        self.config.db_collection = db_collection

        self.config.queue_host = db_host
        self.config.queue_port = 5000
        self.config.queue_size = queue_size
        #self.config.queue_authkey = 'abc'
        self.config.launch_time = time.strftime('%Y-%m-%d %H:%M:%S')
        self.config.pid = os.getpid()
        print('[parallel][TaskQueue] %s' %self.config)
        #print pd.DataFrame(self.config, index=['Queue info']).T
        self.init_queue()


    def init_queue(self):
        self.queue = Queue(maxsize=self.config.queue_size)
        QueueManager.register('get_task_queue', callable=lambda: self.queue)
        manager = QueueManager(address=('', 5000), authkey=b'abc')
        manager.start()
        self.queue_task = manager.get_task_queue()


    def connect_mongodb(self):
        try:
            client = MongoClient(self.config.db_host, self.config.db_port)
            db = client[self.config.db_name]
        except Exception as e:
            print('[parallel][TaskQueue] error: ' + e)
        return db



    def write_queue(self, q, value):
        q.put(value)


    def update_queue(self, data_set):
        for d in data_set:
            self.write_queue(self.queue_task, d)


    def fetch_data(self, col, data_num):
        # 提取数据，优先级降序排列
        #return col.find({"IS_backtest": "Undo"}).sort("priority", pymongo.DESCENDING)[0:data_num]
        print('[parallel][TaskQueue] fetch_data ...')
        return col.find({"backtest": "Undo"})[0:data_num]


    def timing_run(self, queue_threshold):
        from collections import deque
        q_num = deque([], maxlen=10)
        q_time = deque([], maxlen=10)
        while True:
            if self.queue.qsize() <= queue_threshold:
                q_num = deque([], maxlen=10)
                q_time = deque([], maxlen=10)
                db = self.connect_mongodb()
                for i in self.config.db_collection:
                    dataset = self.fetch_data(db[i], data_num=self.config.queue_size)
                    if dataset.count() == 0:
                        print('[parallel][TaskQueue] collection:%s No data fetched from' %i)
                        time.sleep(1)
                    else:
                        print('[parallel][TaskQueue] collection:%s update_queue...' %i)
                        self.update_queue(dataset)
                        time.sleep(1)
                        break
                    
            else:
                q_num.append(self.queue.qsize())
                q_time.append(time.time())
                bar_length = 30
                percent = 1. * self.queue.qsize() / self.config.queue_size
                hashes = '#' * int(percent * bar_length)
                spaces = ' ' * (bar_length - len(hashes))
                sys.stdout.write("\r%s queue volume: %s/%s [%s] %d%% (%s/s)" % (time.strftime('%H:%M'),
                                                                      self.queue.qsize(), self.config.queue_size,
                                                                       hashes + spaces, percent * 100,
                                                                       np.round((q_num[0]-q_num[-1])/(q_time[-1]-q_time[0]+1e-10), 2)))
                sys.stdout.flush()
                time.sleep(0.5)







if __name__ == '__main__':
    Q = TaskQueue(queue_size=5000, db_host='127.0.0.1', db_port=27017, db_name='AutoResearch', 
                db_collection=['layer1', 'layer2', 'layer3', 'layer4', 'layer5', 'layer6', 'layer7'])
    Q.timing_run(queue_threshold=0)
    Q.manager.shutdown()
    print('Queue exit.')


    