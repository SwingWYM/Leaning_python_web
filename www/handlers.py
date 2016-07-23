from coroweb import get,post
from model import User,Blog,Comment
from apis import Page 
import time,asyncio

def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p

@get('/')
def index(request):
    summary = 'Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.'
    blogs = [
        Blog(id='1',name='Test Blog',summary=summary,created_at=time.time()-120),
        Blog(id='2',name='Someting New',summary=summary,created_at=time.time()-3600),
        Blog(id='3',name='Lean Swift',summary=summary,created_at=time.time()-7200)
    ]
    return {
        '__template__' : 'index.html',
        'blogs' : blogs
    }

@get('/api/users')
def api_get_isers():
    users = yield from User.findAll(orderBy='created_at desc')
    for u in users:
        u.passwd = '****'
    return dict(users=users)




@get('/register')
def register():
    return {
        '__template__' : 'register.html'
    }

@post('/api/users')
def api_register_user(*,email,name,passwd):
    pass