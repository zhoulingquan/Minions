export const providerIcon = (provider: string) => {
  switch (provider) {
    case "deepseek":
      return "https://gw.alicdn.com/imgextra/i4/O1CN01YfmXc81ogO3pR0aW8_!!6000000005254-2-tps-400-400.png";
    case "minions-local":
      return "https://gw.alicdn.com/imgextra/i2/O1CN01pyXzjQ1EL1PuZMlSd_!!6000000000334-2-tps-288-288.png";
    case "ollama":
      return "https://gw.alicdn.com/imgextra/i3/O1CN01xZeNJ01R0Ufb3nqqb_!!6000000002049-2-tps-400-400.png";
    case "lmstudio":
      return "https://gw.alicdn.com/imgextra/i4/O1CN01Abv67y1jHaXLqikIJ_!!6000000004523-2-tps-200-200.png";
    default:
      return "https://gw.alicdn.com/imgextra/i4/O1CN01IWnlOw1lebfpiFrIL_!!6000000004844-0-tps-100-100.jpg";
  }
};
