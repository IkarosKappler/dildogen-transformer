import dayjs from "dayjs";

export const uniqueId = (): string => {
  const dateStr = dayjs().format("YYYYMMDD-HHmmss");
  const randomStr = `${Math.floor(Math.random() * 65535)}`;
  return dateStr + "-" + randomStr;
};
