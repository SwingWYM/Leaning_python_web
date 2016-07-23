import logging;logging.basicConfig(level=logging.INFO)

import asyncio, os, json, time
from datetime import datetime

from aiohttp import web

import orm
from model import User,Blog,Comment
from jinja2 import Environment,FileSystemLoader
from coroweb import add_routes,add_static
from config import configs

#jinja2是MVC的V,获取html模版
def init_jinja2(app,**kw):
	logging.info('init jinja2...')
	options = dict(
		autoescape = kw.get('autoescape',True),
		block_start_string = kw.get('block_start_string','{%'),
		block_end_string = kw.get('block_end_string','%}'),
		variable_start_string = kw.get('variable_start_string','{{'),
		variable_end_string = kw.get('variable_end_string','}}'),
		auto_reload = kw.get('auto_reload',True)
	)
	path = kw.get('path',None)
	print('jinja kw',kw)
	if path is None:
		path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'templates')
		logging.info('set jinja2 template path %s' % path)
		env = Environment(loader=FileSystemLoader(path),**options)
		filters = kw.get('filters',None)
		if filters is not None:
			for name,f in filters.items():
				env.filters[name] = f
		print('****',env.get_template)
		app['__templating__'] = env

@asyncio.coroutine
def logger_factory(app,handler):
	@asyncio.coroutine
	def logger(request):
		logging.info('Request:%s %s' % (request.method,request.path))
		return(yield from handler(request))
	return logger

@asyncio.coroutine
def data_factory(app,handler):
	@asyncio.coroutine
	def parse_data(request):
		if request.method == 'POST':
			if request.content_type.startwith('application/json'):
				request.__data__ = yield from request.json()
				logging.info('request json:%s' % str(request.__data__))
			elif request.content_type.startwith('application/x-www-form-urlencoded'):
				request.__data__ = yield from request.post()
				logging.info('request form:%s' % str(request.__data__))
		return(yield from handler(request))
	return parse_data

@asyncio.coroutine
def response_factory(app,handler):
	@asyncio.coroutine
	def reponse(request):
		logging.info('Request handler...')
		r = yield from handler(request)
		if isinstance(r,web.StreamResponse):
			return r
		if isinstance(r,bytes):
			resp = web.Response(body = r)
			resp.content_type = 'application/octet-stream'
			return resp
		if isinstance(r,str):
			if r.startwith('rediredt'):
				return web.HTTPFound(r[9:])
			resp = web.Response(body = r.encode('utf-8'))
			resp.content_type = 'text/html;charset=utf-8'
			return resp
		if isinstance(r,dict):
			template = r.get('__template__')
			if template is None:
				resp = web.Response(body=json.dumps(r,ensure_ascii=False,default=lambda o:o.__dict__).encode('utf-8'))
				resp.content_type = 'application/json;charset=utf-8'
				return resp
			else:
				resp = web.Response(body=app['__templating__'].get_template(template).render(**r).encode('utf-8'))
				resp.content_type = 'text/html;charset=utf-8'
				return resp
		if isinstance(r,int) and r >= 100 and r < 600:
			return web.Response(r)
		if isinstance(r,tuple) and len(r) == 2:
			t,m = r
			if isinstance(r,int) and t >= 100 and t < 600:
				return web.Response(t,str(m))
		resp = web.Response(body=str(r).encode('utf-8'))
		resp.content_type = 'text/plain;charset=utf-8'
		return resp
	return reponse


def datetime_filter(t):
	delta = int(time.time() - t)
	if delta < 60:
		return u'1分钟前'
	if delta < 3600:
		return u'%s分钟前' % (delta // 60)#//表示整数除法，／表示浮点数除法
	if delta < 86400:
		return u'%s小时前' % (delta // 3600)
	if delta < 604800:
		return u'%s天前' % (delta // 86400)
	dt = datetime.fromtimestamp(t)
	return u'%s年%s月%s日' % (dt.year,dt.month,dt.day)


def index(request):
	return web.Response(body = b'<h1>Awesome</h1>')

@asyncio.coroutine
def init(loop):
	yield from orm.create_pool(loop=loop, **configs.db)
	# newuser = User(name='Swing',email='s',passwd='2',image='s')
	# change = User(id='001467343688619174325bd9bee467fa5ee11265c3218f3000',name='Swing',email='18868824506@163.com',passwd='SwingP',image='about:blank',admin=True)
	# yield from change.update()
	# users = yield from User.findAll()
	# print(users)
	# print(type(users))
	# auser = yield from User.find(2)
	# print(auser)
	#中间件：在进行URL处理之前截获，通过handler(request)使之继续进行（也就是执行RequestHandler）
	app = web.Application(loop = loop,middlewares=[
			logger_factory,response_factory
		])
	init_jinja2(app,filters=dict(datetime=datetime_filter))
	add_routes(app,'handlers')
	add_static(app)
	# app.router.add_route('GET','/',index)
	srv = yield from loop.create_server(app.make_handler(),'10.1.15.40',9000)
	logging.info('server started at http://10.1.15.40:9000...')
	return srv
	

loop = asyncio.get_event_loop()
loop.run_until_complete(init(loop))
loop.run_forever()