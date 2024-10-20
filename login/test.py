import jwt

def decode_id_token(id_token: str):
    try:
        # id_token을 디코딩. verify_signature는 애플의 공개키로 서명 검증을 원할 때 사용.
        decoded_token = jwt.decode(id_token, options={"verify_signature": False})
        return decoded_token
    except jwt.InvalidTokenError:
        raise Exception("Invalid ID token")

# 애플로부터 받은 id_token을 여기에 넣어 디코딩합니다.
id_token = 'eyJraWQiOiJwZ2duUWVOQ09VIiwiYWxnIjoiUlMyNTYifQ.eyJpc3MiOiJodHRwczovL2FwcGxlaWQuYXBwbGUuY29tIiwiYXVkIjoiY29tLmRhbGRhLm1hcGRhIiwiZXhwIjoxNzI5NDk0MzY5LCJpYXQiOjE3Mjk0MDc5NjksInN1YiI6IjAwMTUyMC5mNzUzNjI3MzkwYzQ0NzdjOGIxMmE0NmU4MjQzMzI1Yi4xNDU0IiwiYXRfaGFzaCI6InRNa25mX3RQTFFPZmx2Y0lVQ0ptYnciLCJlbWFpbCI6Inlvb2NodWw4OUBuYXZlci5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZSwiYXV0aF90aW1lIjoxNzI5NDA3OTY4LCJub25jZV9zdXBwb3J0ZWQiOnRydWV9.W4qnsIsCgeUKJFbRgvk06vrwedbTpR2FVt8h11M5xFVbZ-HiEe9zzhaAV65A--HUue3qh5FGiyQIrMdooeTT_Y_9k9MBgGEujlzQUCHjL_ONO7Jr1wrB4w7UFHUpBjyRD3tszZXCsqGfKe7u31svp9ruDggL0yuhg1eu0k-5fV4ZPeVlNEoiTS8MqXv0j9edjLqECpeAc-L8M4VOdPQKkzGiy9tdjuQmBwcLZ8OqqfAq9WIopaNxU7lgD69eTnCwm4EAaESU3hZ5-x5naR0piN4tEGC9dfp41foPFpzS3XbcBOD5BiUj0PUI5LipYajCKx4yxVVRl2rhbdmzgZYUFQ'

# 디코딩된 결과 출력
decoded_token = decode_id_token(id_token)
print(decoded_token)
