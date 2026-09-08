"""
La cache de la app no debe guardar fallos.

Camilo vio el mensaje de error de una version anterior del codigo
porque la cache le devolvia el intento fallido durante quince minutos,
mucho despues de que el bug estuviera arreglado.
"""
import sys, types
sys.path.insert(0, "/home/user/QA_2_Global")

# Un st minimo: solo session_state, que es lo que usa la funcion.
class FakeState(dict):
    def setdefault(self, k, v): return super().setdefault(k, v)

fake_st = types.SimpleNamespace(session_state=FakeState())

class Result:
    def __init__(self, errors): self.errors = errors

calls = {"n": 0}
def fake_fetch(campaign_id, credentials, placement_ids, headless):
    calls["n"] += 1
    # Los dos primeros intentos fallan, el tercero funciona.
    return Result([] if calls["n"] >= 3 else ["Innovid rejected the request"])

# Se reconstruye la funcion tal como quedo en la app.
import time as _time
INNOVID_CACHE_SECONDS = 900
st = fake_st
def cached_fetch_innovid(campaign_id, placement_ids):
    key = (str(campaign_id), tuple(placement_ids))
    store = st.session_state.setdefault("qa2_innovid_cache", {})
    hit = store.get(key)
    if hit and (_time.monotonic() - hit[0]) < INNOVID_CACHE_SECONDS:
        return hit[1]
    result = fake_fetch(campaign_id, None, placement_ids, True)
    if not result.errors:
        store[key] = (_time.monotonic(), result)
    else:
        store.pop(key, None)
    return result

fails = []
def check(label, got, want=True):
    if got != want: fails.append(label); print(f"  FAIL {label}: {got!r}")
    else: print(f"  ok   {label}")

ids = ("11102553", "11102546")

r1 = cached_fetch_innovid("328634", ids)
check("first attempt fails", bool(r1.errors))
r2 = cached_fetch_innovid("328634", ids)
check("a failure is retried, not replayed", calls["n"], 2)
check("still failing", bool(r2.errors))

r3 = cached_fetch_innovid("328634", ids)
check("the third attempt succeeds", r3.errors, [])
check("it actually called again", calls["n"], 3)

r4 = cached_fetch_innovid("328634", ids)
check("a success IS reused", calls["n"], 3)
check("and is the same result", r4 is r3)

cached_fetch_innovid("328634", ("99999",))
check("a different placement set refetches", calls["n"], 4)

print()
if fails: print(f"{len(fails)} FAILURE(S): {fails}"); sys.exit(1)
print("Cache behaviour verified.")
