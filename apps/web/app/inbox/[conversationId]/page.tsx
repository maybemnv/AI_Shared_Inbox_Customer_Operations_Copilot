import { InboxWorkbench } from "../../../components/InboxWorkbench";

export default async function ConversationPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;
  return <InboxWorkbench initialConversationId={conversationId} />;
}
