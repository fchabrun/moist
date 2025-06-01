import pandas as pd
import numpy as np

def remap_value_by_state(val, state):
    if state == ">3":
        if val > 3:
            return val
        return np.nan
    if state == "<=3":
        if val <= 3:
            return val
        return np.nan

test = pd.Series([1., 2, 3, 2, 1, 3, 6, 1, 2, 1, 3, 4, 5, 7, 9, 5, 11, 6, 2, 7, 4, 2, 1, 2, 3], name="sensor_0")

print(f'{test=}')

print(f"{test.map(lambda val: remap_value_by_state(val, state='>3'))=}")
print(f"{test.map(lambda val: remap_value_by_state(val, state='<=3'))=}")

print(f"{test.map(lambda val: remap_value_by_state(val, state='>3')).fillna(value=test, limit=1)=}")
print(f"{test.map(lambda val: remap_value_by_state(val, state='<=3')).fillna(value=test, limit=1)=}")
