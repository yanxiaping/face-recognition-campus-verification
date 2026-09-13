Page({
  data: {
    historyList: []
  },
  onShow() {
    // 页面显示时，从后端加载最新记录
    this.loadHistoryFromServer();
  },
  // 从后端接口加载历史记录（核心）
  loadHistoryFromServer() {
    let that = this;
    wx.request({
      // 这里必须换成你电脑的【局域网IP】
      url: "http://172.20.10.3:5000/api/history", 
      method: "GET",
      success(res) {
        if (res.statusCode === 200) {
          let serverList = res.data || [];
          let localList = wx.getStorageSync('faceHistory') || [];
          // 合并本地图片路径到后端数据
          serverList = serverList.map((item, idx) => {
            if(localList[idx] && localList[idx].img){
              item.img = localList[idx].img;
            }
            return item;
          })
          // 限制最多显示50条
          serverList = serverList.slice(0, 50);
          that.setData({
            historyList: serverList
          });
        }
      },
      fail(err) {
        console.log("加载失败", err);
        // 加载失败时，显示本地缓存兜底
        let localData = wx.getStorageSync('faceHistory') || [];
        localData = localData.slice(0, 50);
        that.setData({
          historyList: localData
        });
      }
    });
  }
});