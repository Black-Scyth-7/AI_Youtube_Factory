import { Button, Input } from "@ayf/ui";

/** Placeholder admin sign-in. Authentication ships in a later phase. */
export default function AdminLoginPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-center text-xl font-semibold">Admin sign in</h1>
      <form className="space-y-3" aria-disabled>
        <Input type="email" placeholder="admin@example.com" disabled />
        <Input type="password" placeholder="Password" disabled />
        <Button type="button" className="w-full" disabled>
          Sign in
        </Button>
      </form>
    </div>
  );
}
