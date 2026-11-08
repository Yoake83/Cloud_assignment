"""Cold-start measurement (Task 4, step 7): delete all pods, wait for Ready, repeat 3 times.
Per run we report the slowest pod (creation -> Ready), and the median of the three runs."""
import json
import statistics
import subprocess
import time
from datetime import datetime

NS = "app"


def kubectl(*args):
    return subprocess.run(["kubectl", "-n", NS, *args], check=True, capture_output=True, text=True).stdout


def ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def pod_times():
    out = json.loads(kubectl("get", "pods", "-l", "app=cmdparser", "-o", "json"))
    times = []
    for p in out["items"]:
        ready = next((c for c in p["status"].get("conditions", []) if c["type"] == "Ready"), None)
        if ready and ready["status"] == "True":
            times.append((ts(ready["lastTransitionTime"]) - ts(p["metadata"]["creationTimestamp"])).total_seconds())
    return times


runs = []
for i in range(1, 4):
    kubectl("delete", "pods", "-l", "app=cmdparser", "--wait=true")
    want = json.loads(kubectl("get", "deployment", "cmdparser", "-o", "json"))["spec"]["replicas"]
    t0 = time.time()
    while True:
        times = pod_times()
        if len(times) >= want:
            break
        if time.time() - t0 > 600:
            raise SystemExit("timed out waiting for pods to become Ready")
        time.sleep(2)
    print(f"run {i}: per-pod creation->Ready seconds = {times}; slowest = {max(times)}")
    print(kubectl("logs", "-l", "app=cmdparser", "--tail=5", "--prefix=true"))
    runs.append(max(times))
print("runs:", runs, "median:", statistics.median(runs))
