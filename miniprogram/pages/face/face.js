Page({
  data: {
    isDetecting: false,
    isRecognized: false,
    resultMsg: "请将人脸对准识别框",
    resultType: "",
    timer: null,
    API_URL: "http://172.20.10.3:5000/api/recognize",
    successLock: false,
    isSleeping: false,
    screenDark: false,
    noFaceCount: 0,
    currentImgPath: ""
  },

  tapScreenWake() {
    if (!this.data.isSleeping) return;
    this.setData({
      isSleeping: false,
      screenDark: false,
      noFaceCount: 0,
      resultMsg: "已唤醒，请将人脸对准识别框"
    });
    this.startRecognize();
  },

  onShow() {
    this.setData({
      isDetecting: false,
      successLock: false,
      isSleeping: false,
      screenDark: false,
      noFaceCount: 0
    });
    clearInterval(this.data.timer);
    this.startAutoDetect();
  },

  onHide() {
    clearInterval(this.data.timer);
    this.setData({ timer: null });
  },

  onLoad(options) {
    this.applyCameraAuth();
  },

  onUnload() {
    this.onHide();
  },

  applyCameraAuth() {
    wx.authorize({
      scope: 'scope.camera'
    });
  },

  cameraError(e) {
    console.error("相机错误", e);
  },

  startRecognize() {
    if (this.data.isSleeping || this.data.successLock || this.data.isDetecting) return;
    this.setData({
      isDetecting: true,
      resultMsg: "正在识别中...",
      resultType: ""
    });
    this.captureImage();
  },

  captureImage() {
    const that = this;
    if (this.data.isSleeping) return;

    wx.createCameraContext().takePhoto({
      quality: "normal",
      success: (res) => {
        const tempImgPath = res.tempImagePath;
        that.setData({ currentImgPath: tempImgPath });

        wx.getFileSystemManager().readFile({
          filePath: tempImgPath,
          encoding: "base64",
          success: (data) => {
            that.sendToBackend(data.data);
          },
          fail: () => {
            that.setData({
              isDetecting: false,
              resultMsg: "图片处理失败",
              resultType: "fail"
            });
          }
        });
      },

      fail: () => {
        let count = that.data.noFaceCount + 1;
        if (count >= 10) {
          setTimeout(() => {
            that.setData({
              isSleeping: true,
              screenDark: true,
              resultMsg: "等待人脸进入识别区域，点击屏幕唤醒"
            });
          }, 600);
        } else {
          that.setData({ noFaceCount: count });
        }

        that.setData({
          isDetecting: false,
          resultMsg: "未检测到人脸",
          resultType: "fail"
        });
      }
    });
  },

  sendToBackend(base64Data) {
    const that = this;
    wx.request({
      url: this.data.API_URL,
      method: "POST",
      header: { "Content-Type": "application/json" },
      data: { image_base64: base64Data },
      success: (res) => {
        that.handleRecognitionResult(res.data);
      },
      fail: () => {
        that.setData({
          isDetecting: false,
          resultMsg: "连接服务器失败",
          resultType: "fail"
        });
      }
    });
  },

  handleRecognitionResult(result) {
    this.setData({ isDetecting: false });
    const tempImgPath = this.data.currentImgPath || "";

    // 仅识别成功时，才写入历史记录
    if (result.allow_open) {
      this.setData({ noFaceCount: 0 });
      let history = wx.getStorageSync("faceHistory") || [];
      const savePath = wx.env.USER_DATA_PATH + `/face_${Date.now()}.jpg`;

      if (tempImgPath) {
        wx.saveFile({
          tempFilePath: tempImgPath,
          filePath: savePath,
          success: () => {
            history.unshift({
              name: result.name,
              student_id: result.student_id,
              time: new Date().toLocaleString(),
              message: `识别成功：${result.name}`,
              img: savePath
            });
            history = history.slice(0, 50);
            wx.setStorageSync("faceHistory", history);
          },
          fail: () => {
            history.unshift({
              name: result.name,
              student_id: result.student_id,
              time: new Date().toLocaleString(),
              message: `识别成功：${result.name}`,
              img: ""
            });
            history = history.slice(0, 50);
            wx.setStorageSync("faceHistory", history);
          }
        });
      }

      this.setData({
        resultMsg: `欢迎 ${result.name}（${result.student_id}），开门成功！`,
        resultType: "success",
        successLock: true
      });
      setTimeout(() => {
        this.setData({ successLock: false });
      }, 1000);
      return;
    }

    // ========== 陌生人/未识别人脸：【不再写入历史】，只走计数、休眠逻辑 ==========
    this.setData({
      resultMsg: "未检测到人脸",
      resultType: "fail"
    });
    let count = this.data.noFaceCount + 1;
    if (count >= 10) {
      setTimeout(() => {
        this.setData({
          isSleeping: true,
          screenDark: true,
          resultMsg: "等待人脸进入识别区域，点击屏幕唤醒"
        });
      }, 600);
    } else {
      this.setData({ noFaceCount: count });
    }
  },

  startAutoDetect() {
    if (this.data.timer) return;
    const timer = setInterval(() => {
      if (!this.data.isDetecting && !this.data.successLock && !this.data.isSleeping) {
        this.startRecognize();
      }
    }, 800);
    this.setData({ timer: timer });
  },

  goToHistory() {
    wx.navigateTo({
      url: '/pages/history/history'
    })
  }
});