import { notFound } from "next/navigation";
import { DayView } from "@/components/DayView";
import { userTz } from "@/lib/api";

export default async function Day({ params, searchParams }: { params: Promise<{ date: string }>; searchParams: Promise<{ league?: string }> }) {
  const { date } = await params;
  const { league } = await searchParams;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) notFound();
  return <DayView day={date} tz={await userTz()} league={league} />;
}
