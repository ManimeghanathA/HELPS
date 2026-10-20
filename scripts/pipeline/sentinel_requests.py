"""Serialize Process API calls and honor CDSE's millisecond Retry-After header."""
import math
import time
from threading import Lock
import requests

PROCESS_URL='https://sh.dataspace.copernicus.eu/api/v1/process'
_lock=Lock()
_last_request=0.0


def process_request(session,payload,token,log=print,timeout=(10,180),max_attempts=6):
    global _last_request
    with _lock:
        waited=0.0
        for attempt in range(max_attempts):
            pause=max(0.0,1.0-(time.monotonic()-_last_request))
            if pause:time.sleep(pause)
            _last_request=time.monotonic()
            try:
                response=session.post(PROCESS_URL,json=payload,
                    headers={'Authorization':'Bearer '+token,'Accept':'image/tiff'},timeout=timeout)
            except (requests.Timeout,requests.ConnectionError):
                if attempt+1==max_attempts:raise
                delay=min(60.0,2.0**(attempt+1))
                log(f'Sentinel connection interrupted; waiting {delay:.1f}s before retry {attempt+2}/{max_attempts}')
                time.sleep(delay);waited+=delay;continue
            status=getattr(response,'status_code',200)
            if status not in (429,502,503,504):
                response.raise_for_status();return response
            delay=min(60.0,2.0**(attempt+1))
            if status==429:
                try:
                    provider_delay=float(getattr(response,'headers',{}).get('Retry-After',''))/1000
                    if math.isfinite(provider_delay) and provider_delay>=0:delay=max(delay,provider_delay)
                except (ValueError,TypeError):pass
            if attempt+1==max_attempts or waited+delay>300:
                message=('Sentinel provider rate limit persists. Completed tiles are preserved; retry this date later.'
                    if status==429 else 'Sentinel provider remains unavailable. Completed tiles are preserved; retry later.')
                raise requests.HTTPError(message,response=response)
            log(f'Sentinel {"rate limit" if status==429 else "provider interruption"}: waiting {delay:.1f}s before retry {attempt+2}/{max_attempts}; completed tiles are retained')
            if hasattr(response,'close'):response.close()
            time.sleep(delay);waited+=delay
    raise ValueError('Sentinel request attempts exhausted')
