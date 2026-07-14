const defaultConfig = {
  theme: {
    colorPrimary: "#FF7F16",
    darkMode: false,
    prefix: "minions",
    leftHeader: {
      logo: "",
      title: "Work with Minions",
    },
    bubbleList: {
      userMessageAnchors: {
        variant: "navigator",
      },
    },
  },
  sender: {
    attachments: true,
    maxLength: 10000,
    longTextUpload: {
      enabled: true,
    },
    disclaimer: "懂你所需，伴你左右",
  },
  welcome: {
    greeting: "你好，我今天能帮你做什么？",
    description:
      "我是一个智能助手，可以帮助你解答问题。",
    avatar: "/online.svg",
    prompts: [
      {
        value: "让我们开启一段新的旅程吧！",
      },
      {
        value: "能告诉我你有哪些技能吗？",
      },
    ],
  },
  api: {
    baseURL: "",
    token: "",
  },
} as const;

export default defaultConfig;

export type DefaultConfig = typeof defaultConfig;
