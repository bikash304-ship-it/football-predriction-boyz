import { DayView } from "@/components/DayView";
import { userTz } from "@/lib/api";
import { todayIn } from "@/lib/format";

export const metadata = { title: "Tomorrow" };

export default async function Tomorrow({ searchParams }: { searchParams: Promise<{ league?: string }> }) {
  const tz = await userTz();
  const { league } = await searchParams;
  return <DayView day={todayIn(tz, 1)} tz={tz} league={league} />;
}
