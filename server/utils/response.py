from datetime import datetime
from fastapi.responses import JSONResponse

class APIException(Exception):
    def __init__(self, detail: str, status: str = "error"):
        super().__init__(detail)
        self.detail = detail
        self.status = status

def make_response(data=None, msg='', status='success'):
    """统一的响应格式
    
    Args:
        data: 返回的数据
        msg: 返回的消息，默认为空字符串
        status: 状态，默认为'success'
        
    Returns:
        JSONResponse：
        {
            'status': 'success' | 'error',
            'data': Any,
            'message': str
        }
    """
    status_code = 200 if status == 'success' else 400
    return JSONResponse(status_code=status_code, content={
        'status': status,
        'data': data,
        'message': msg,
    })

