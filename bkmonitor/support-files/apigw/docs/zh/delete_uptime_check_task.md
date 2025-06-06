### 功能描述

删除拨测任务


#### 接口参数

| 字段      | 类型  | 必选 | 描述     |
|---------|-----|----|--------|
| task_id | int | 是  | 拨测任务ID |

#### 示例数据

```json
{
  "task_id": 10002
}
```

### 响应参数

| 字段      | 类型   | 描述     |
|---------|------|--------|
| result  | bool | 请求是否成功 |
| code    | int  | 返回的状态码 |
| message | str  | 描述信息   |
| data    | dict | 数据     |

#### data

| 字段     | 类型  | 描述     |
|--------|-----|--------|
| id     | int | 拨测任务ID |
| result | str | 描述信息   |

#### 示例数据

```json
{
  "result": true,
  "code": 200,
  "message": "OK",
  "data": {
    "id": 10002,
    "result": "删除成功"
  }
}
```
