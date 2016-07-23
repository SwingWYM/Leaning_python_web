
import asyncio
import os,logging
import functools,inspect
from apis import APIError

def get(path):
	'''
	Define decorator @get(/path)
	'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args,**kw):
			return func(*args,**kw)
		wrapper.__method__ = 'GET'
		wrapper.__route__ = path
		return wrapper
	return decorator


def post(path):
	'''
	Define decorator @post(/path)
	'''
	def decorator(func):
		@functools.wraps(func)
		def wrapper(*args,**kw):
			return func(*args,**kw)
		wrapper.__method__ = 'POST'
		wrapper.__route__ = path
		return wrapper
	return decorator
#以上两个是装饰器，在handlers.py里面的URL请求会使用


#fn指的是handler里面的URL请求函数，这个函数获得需要传入的命名关键字参数
def get_required_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY and param.default == inspect.Parameter.empty:
			args.append(name)
	return tuple(args)

#获得所有的命名关键词参数。
def get_named_kw_args(fn):
	args = []
	params = inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			args.append(name)
	return tuple(args)

#是否有命名关键字参数
def has_named_kw_args(fn):
	params = inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind == inspect.Parameter.KEYWORD_ONLY:
			return True

#是否有关键字参数
def has_var_kw_arg(fn):
	params = inspect.signature(fn).parameters
	for name,param in params.items():
		if param.kind == inspect.Parameter.VAR_KEYWORD:
			return True

#参数里面是否有request
def has_request_arg(fn):
	sig = inspect.signature(fn)
	params = sig.parameters
	found = False
	for name,param in params.items():
		if name == 'request':
			found = True
			continue
		if found and (param.kind != inspect.Parameter.VAR_POSITIONAL and param.kind != inspect.Parameter.KEYWORD_ONLY and param.kind != inspect.Parameter.VAR_KEYWORD):
			raise ValueError('request parameter must be the last named parameter in function: %s%s' % (fn.__name__, str(sig)))
	return found

class RequestHandler(object):
	def __init__(self,app,fn):
		self._app = app
		self._func = fn
		self._has_request_arg = has_request_arg(fn)
		self._has_var_kw_arg = has_var_kw_arg(fn)
		self._has_named_kw_args = has_named_kw_args(fn)
		self._named_kw_args = get_named_kw_args(fn)
		self._required_kw_args = get_required_kw_args(fn)

	@asyncio.coroutine
	def __call__(self,request):
		kw = None
		if self._has_var_kw_arg or self._has_named_kw_args or self._required_kw_args:
			if request.method == 'POST':
				print('*****POST')
				if not request.content_type:#request.content_type代表了不同的类型，比如上传文件图片的时候需要用来判断
					return web.HTTPBadRequest('Missing Content-Type')
				ct = request.content_type.lower()
				if ct.startswith('application/json'):#startswith是string里面的用法
					params = yield from request.json()
					if not isinstance(params,dict):
						return web.HTTPBadRequest('JSON body must be object')
					kw = params
					print('application/json',params)
				elif ct.startswith('application/x-wwww-form-urlencoded') or ct.startswith('multipart/form-data'):
					params = yield from request.post()
					kw = dict(**params)
					print('application/x-wwww-form-urlencoded',params)
				else:
					return web.HTTPBadRequest('Unsupported Content-Type:%s' % request.content_type)
			if request.method == 'GET':
				qs = request.query_string#如果是通过query的方式就会获得，否则qs为空
				print('******GET qs',qs)
				if qs:
					kw = dict()
					for k,v in parse.parse_qs(qs,True).items():
						kw[k] = v[0]
		#kw保持request里面的从前端传来的参数
		if kw is None:
			kw = dict(**request.match_info)
			print('request.match_info',request.match_info)
		else:
			if not self._has_var_kw_arg and self._named_kw_args:#如果只可能有命名关键字
				copy = dict()
				for name in self._named_kw_args:
					if name in kw:
						copy[name] = kw[name]
				kw = copy#从request里面获得饿所需的命名关键字参数
			for k,v in request.match_info.items():
				if k in kw:
					logging.warning('Duplicate arg name in named arg and kw args:%s' % k)
				kw[k] = v
		if self._has_request_arg:
			kw['request'] = request
		if self._required_kw_args:
			for name in self._required_kw_args:
				if not name in kw:
					return HTTPBadRequest('Missing argument:%s' % name)
		#kw里面保存URL处理函数所需要的参数
		logging.info('call with args:%s' % str(kw))
		try:
			r = yield from self._func(**kw)
			return r
		except APIError as e:
			return dict(error=e.error,data=e.data,message=e.message)

def add_static(app):
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)),'static')
	app.router.add_static('/static/',path)
	logging.info('add static %s=>%s' % ('/static/',path))

def add_route(app,fn):
	method = getattr(fn,'__method__',None)
	path = getattr(fn,'__route__',None)
	if path is None or method is None:
		raise ValueError('@get or @post not defined in %s' % str(fn))
		#不是异步函数也不是迭代函数，才对他进行异步操作
	if not asyncio.iscoroutinefunction(fn) and not inspect.isgeneratorfunction(fn):
		fn = asyncio.coroutine(fn)
	logging.info('add route %s %s => %s(%s)' % (method,path,fn.__name__,', '.join(inspect.signature(fn).parameters.keys())))
	app.router.add_route(method,path,RequestHandler(app,fn))

def add_routes(app,module_name):
	n = module_name.rfind('.')
	if n == (-1):
		mod = __import__(module_name,globals(),locals())
	else:
		name = module_name[n + 1:]
		#动态导入模版，并获得模版中的name类
		mod = getattr(__import__(module_name[:n],globals(),[name]),name)
	for attr in dir(mod):#获得mod中的所有属性和方法
		if attr.startswith('_'):
			continue
		fn = getattr(mod,attr)#获得mod中名为的attr属性或者方法
		if callable(fn):#判断fn是否为函数
			method = getattr(fn,'__method__',None)
			path = getattr(fn,'__route__',None)
			#当该函数有method和path才认为是我们需要的处理URL的函数
			if method and path:
				add_route(app,fn)