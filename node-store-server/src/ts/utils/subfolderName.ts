import dayjs from "dayjs";

export const subfolderName = (): string => {
  const dateStr = dayjs().format("YYYY[/]MM");
  return dateStr;
};
