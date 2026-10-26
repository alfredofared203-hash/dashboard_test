import { Button as ShadcnButton, type ButtonProps } from "@/components/ui/button";

export type ActionButtonProps = ButtonProps;

export function ActionButton(props: ActionButtonProps) {
  return <ShadcnButton {...props} />;
}
