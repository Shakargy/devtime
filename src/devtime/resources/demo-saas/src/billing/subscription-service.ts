export async function updateSubscriptionState(subscription: any): Promise<void> {
  // Maps a Stripe subscription onto local subscription state.
  const status = subscription.status;
  const customerId = subscription.customer;
  await saveSubscription(customerId, status);
}

async function saveSubscription(customerId: string, status: string) {
  // Persistence omitted for the demo.
  return { customerId, status };
}
