import { DayView } from "@/components/DayView";
import { userTz } from "@/lib/api";
import { todayIn } from "@/lib/format";

export const metadata = { title: "Today" };

export default async function Today({ searchParams }: { searchParams: Promise<{ league?: string }> }) {
  const tz = await userTz();
  const { league } = await searchParams;
  return <DayView day={todayIn(tz)} tz={tz} league={league} />;
}
