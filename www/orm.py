

import asyncio, logging
import aiomysql

import logging;logging.basicConfig(level=logging.INFO)

# import asyncio, os, json, time
# from datetime import datetime

# from aiohttp import web

def log(sql, args=()):
	logging.info('SQL:%s' % sql)

@asyncio.coroutine
def create_pool(loop,**kw):
	logging.info('create database connection pool..')
	global __pool
	__pool = yield from aiomysql.create_pool(
		host = kw.get('host', 'localhost'),
		port = kw.get('port', 3306),
		user = kw['user'],
		password = kw['password'],
		db = kw['database'],
		charset = kw.get('charset', 'utf8'),
		autocommit = kw.get('aautocommit', True),
		maxsize = kw.get('maxsize', 10),
		minsize = kw.get('minsize', 1),
		loop = loop
	)

@asyncio.coroutine
def select(sql, args, size = None):
	log(sql, args)
	global __pool
	with (yield from __pool) as conn:
		cur = yield from conn.cursor(aiomysql.DictCursor)#aiomysql.DictCursor使得返回键值对
		yield from cur.execute(sql.replace('?','%s'),args or ())
		if size:
			rs = yield from cur.fetchmany(size)
		else:
			rs = yield from cur.fetchall()
		yield from cur.close()
		logging.info('rows returned %s' % len(rs))
		# print(rs)
		return rs

@asyncio.coroutine
def execute(sql, args):
	log(sql)
	with (yield from __pool) as conn:
		try:
			cur = yield from conn.cursor()
			yield from cur.execute(sql.replace('?','%s'),args)
			affected = cur.rowcount
			yield from cur.close()	
		except BaseException as e:
			raise 
		return affected

def create_args_string(num):
	L = []
	for n in range(num):
		L.append('?')
	return ', '.join(L)
 
class ModelMetaclass(type):
	def __new__(cls,name,bases,attrs):
		# 参数cls，代表要实例化的类，此参数在实例化时由Python解释器自动提供，相当于self，指向model，name这里相当于
		#User，bases相当于User的父类，attrs相当于User的属性或者参数的dic
		if name == 'Model':
			return type.__new__(cls,name,bases,attrs)

		tableName = attrs.get('__table__',None) or name
		logging.info('found model:%s (table: %s)' % (name,tableName))
		mappings = dict()
		fields = []
		primaryKey = None
		for k,v in attrs.items():
		#k相当于id和name，v相当于IntegerField等
			if isinstance(v,Field):
				logging.info('  found mapping: %s==> %s' % (k,v))
				mappings[k] = v
				if v.primary_key:
					if primaryKey:
						raise RuntimeError('Duplicate primary key for field: %s' % k)
					primaryKey = k
				else:
					fields.append(k)
					#里面是name，也就是除了主键的属性
		if not primaryKey:
			raise RuntimeError('Primary key not found.')
		for k in mappings.keys():
			attrs.pop(k)
			#清空attrs
		escaped_fields = list(map(lambda f:'`%s`' % f,fields))
		#相当于：[‘｀name｀’]字符串数组
		attrs['__mappings__'] = mappings
		attrs['__table__'] = tableName
		attrs['__primary_key__'] = primaryKey
		attrs['__fields__'] = fields
		attrs['__select__'] = 'select `%s`, %s from `%s`' % (primaryKey,', '.join(escaped_fields),tableName)
		attrs['__insert__'] = 'insert into `%s` (%s, `%s`) values (%s)' % (tableName,', '.join(escaped_fields),primaryKey,create_args_string(len(escaped_fields)+1))
		attrs['__update__'] = 'update `%s` set %s where `%s`=?' % (tableName,', '.join(map(lambda f:'`%s`=?' % (mappings.get(f).name or f), fields)),primaryKey)
		attrs['__delete__'] = 'delete from `%s` where `%s`=?' % (tableName,primaryKey)
		return type.__new__(cls,name,bases,attrs)

								


class Model(dict, metaclass=ModelMetaclass):
	def __init__(self, **kw):
		super(Model, self).__init__(**kw)
		#创建一个dic,使用实例化的时候传入的参数

	def __getattr__(self,key):
		try:
			return self[key]
		except KeyError:
			raise AttributeError(r"'Model' object has no attribute '%s'" % key)

	def __setattr__(self,key,value):
		self[key] = value

	def getValue(self,key):
		return getattr(self,key,None) 
		#原来getattr只对属性有用，由于有了__getattr__，对self[key]也可以获得了


	def getValueOrDefault(self, key):
		value = getattr(self, key, None)
		if value is None:
			field = self.__mappings__[key]
			if field.default is not None:
				value = field.default() if callable(field.default) else field.default
				logging.debug('using default value for %s: %s' % (key, str(value)))
				setattr(self, key, value)
		return value

	@classmethod
	@asyncio.coroutine
	def findAll(cls,where=None,args=None,**kw):
		' find objects by where clause'
		sql = [cls.__select__]
		if where:
			sql.append('where')
			sql.append(where)
		if args is None:
			args = []
		orderBy = kw.get('orderBy',None)
		if orderBy:
			sql.append('order by')
			sql.append(orderBy)
		limit = kw.get('limit',None)
		if limit is not None:
			sql.append('limit')
			if isinstance(limit,int):
				sql.append('?')
				args.append(limit)
			elif isinstance(limit,tuple) and len(limit) == 2:
				sql.append('?, ?')
				args.extend(limit)
			else:
				raise ValueError('Invalid limit value: %s' % str(limit))
		rs = yield from select(' '.join(sql),args)
		# print(rs)
		# print('___________________________________________')
		# for r in rs:
		# 	print(r)
		return [cls(**r) for r in rs]
		# 输出每一个，find返回的是什么

	@classmethod
	@asyncio.coroutine
	def findNumber(cls,selectField,where=None,args=None):
		' find number by select and where'
		sql = ['select %s _num_ from `%s`' % (selectField,cls.__table__)]
		if where:
			sql.append('where')
			sql.append(where)
		rs = yield from select(' '.join(sql),args,1)
		if len(rs) == 0:
			return None
		return rs[0]['_num_']

	@classmethod
	@asyncio.coroutine
	def find(cls,pk):
		' find object by primary key.'
		rs = yield from select('%s where `%s`=?' % (cls.__select__,cls.__primary_key__),[pk],1)
		if len(rs) == 0:
			return None
		return cls(**rs[0])

	# @classmethod
	@asyncio.coroutine
	def save(self):
		# print(self.__fields__)
		args = list(map(self.getValueOrDefault, self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		print(args)
		rows = yield from execute(self.__insert__,args)
		if rows != 1:
			logging.warn('faild to insert record:affected rows; %s' % rows)

	@asyncio.coroutine
	def update(self):
		args = list(map(self.getValueOrDefault,self.__fields__))
		args.append(self.getValueOrDefault(self.__primary_key__))
		print(args)
		rows = yield from execute(self.__update__,args)
		if rows != 1:
			logging.warn('faild to update by primary key:aeected rows: %s' % rows)

	@asyncio.coroutine
	def remove(self):
		args = [self.getValue(self.__primary_key__)]
		rows = yield from execute(self.__delete__,args)
		if rows != 1:
			logging.warn('faild to remove by primary key:effected rows:%s' % rows)
			


class Field(object):
	def __init__(self,name, column_type,primary_key,default):
		self.name = name
		self.column_type = column_type
		self.primary_key = primary_key
		self.default = default

	def __str__(self):
		return '<%s,%s:%s>' % (self.__class__.__name__,self.column_type,self.name)

class StringField(Field):
	def __init__(self,name=None,primary_key=False,default=None,ddl='varchar(100)'):
		super().__init__(name,ddl,primary_key,default)

class BooleanField(Field):
	def __init__(self,name=None,default=False):
		super().__init__(name,'boolean',False,default)

class IntegerField(Field):
	def __init__(self,name=None,primary_key=False,default=0):
		super().__init__(name,'bigint',primary_key,default)
		
class FloatField(Field):
	def __init__(self,name=None,primary_key=False,default=0.0):
		super().__init__(name,'real',primary_key,default)

class TextField(Field):
	def __init__(self, name=None,default=None):
		super().__init__(name,'text',False,default)
		
		
		
		
#一开始不知道怎么启动create，其实create跟其他操作函数都放在一个函数里面就可以。先create，再操作其他函数
#后来无法连接到数据库
#后来其实成功了，由于没有logging，导致没有输出
# class User(Model):
# 	__table__ = 'users'
# 	id = IntegerField(primary_key=True)
# 	name = StringField()


# configs = {
#     'debug': True,
#     'db': {
#         'host': '127.0.0.1',
#         'port': 3306,
#         'user': 'root',
#         'password': 'password',
#         'db': 'test'
#     },
#     'session': {
#         'secret': 'Awesome'
#     }
# }



# @asyncio.coroutine
# def init(loop):
# 	# yield from create_pool(loop=loop, **configs['db'])
# 	yield from create_pool(loop,user='root',password='password',db='test',port=3306,host='127.0.0.1')
# 	users = yield from User.findAll()
# 	print(users)
# 	# newuser = User(id = 12345,name = 'swing')
# 	# yield from newuser.save()
# 	# users = yield from User.findAll()
# 	# print(users)
# 	change = User(id = 1234,name = 'lafido')
# 	yield from change.update()
# 	users = yield from User.findAll()
# 	print(users)

# loop = asyncio.get_event_loop()
# loop.run_until_complete(init(loop))
# loop.run_forever()


