import { CustomerSurface } from "../../../components/FixtureSurface";

export default async function CustomerPage({ params }: { params: Promise<{ customerId: string }> }) {
  const { customerId } = await params;
  return <CustomerSurface customerId={customerId} />;
}
