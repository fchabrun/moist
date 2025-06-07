import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.signal import savgol_filter

n_values_to_generate = 1000000
n_values_to_plot = 1000
ewm_alpha = .0001

data = pd.concat([pd.Series([datetime.now() - timedelta(seconds=n_values_to_generate-i) for i in range(n_values_to_generate)], name="time"),
                  pd.Series(300 + 10 * np.sin(np.arange(n_values_to_generate) / (0.1 * n_values_to_generate)) + np.random.normal(loc=0, scale=5, size=n_values_to_generate), name="humidity")], axis=1)

data["time_in_seconds"] = (data["time"] - data["time"].max()) / timedelta(seconds=1)

new_time = np.linspace(data.time_in_seconds.min(), data.time_in_seconds.max(), num=n_values_to_plot)

# smooth TODO let the user choose their alpha, with default .01
data["humidity_smooth"] = data.humidity.ewm(alpha=ewm_alpha).mean()
# interpolate to reduce the number of values
new_humidity = np.interp(x=np.linspace(data.time_in_seconds.min(), data.time_in_seconds.max(), num=n_values_to_plot), xp=data.time_in_seconds, fp=data.humidity)
new_humidity_smooth = np.interp(x=np.linspace(data.time_in_seconds.min(), data.time_in_seconds.max(), num=n_values_to_plot), xp=data.time_in_seconds, fp=data.humidity_smooth)
data_plot = pd.concat([pd.Series(new_time, name="time_in_seconds"),
                       pd.Series(new_humidity, name="humidity"),
                       pd.Series(new_humidity_smooth, name="humidity_smooth")], axis=1)

# plot
plt.figure(figsize = (16,8))
sns.lineplot(data=data_plot, x="time_in_seconds", y="humidity")
sns.lineplot(data=data_plot, x="time_in_seconds", y="humidity_smooth")
plt.tight_layout()
plt.show()