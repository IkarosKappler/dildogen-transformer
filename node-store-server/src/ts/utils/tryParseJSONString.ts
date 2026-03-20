export const tryParseJSONString = (jsonString: string, fallback: object): object => {
  try {
    return JSON.parse(jsonString);
  } catch (e) {
    return fallback;
  }
};
