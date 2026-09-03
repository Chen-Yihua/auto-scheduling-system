class NonRetryableError(Exception):
    """
    代表「重試也沒用」的失敗，例如帳密/token 錯誤、找不到資源這類客戶端錯誤——
    再打一次還是同樣的結果。跟一般 Exception（視為暫時性失敗，例如 5xx、
    rate limit、逾時、網路抖動）分開，讓 crud/external_sync.py 的重試邏輯
    可以判斷要不要浪費時間重試，還是直接放棄、退回快取。
    """
    pass
