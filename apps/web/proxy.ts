import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const username = "miguel";

function unauthorized() {
  return new NextResponse("Authentication required.", {
    status: 401,
    headers: {
      "WWW-Authenticate": 'Basic realm="PolyEdge", charset="UTF-8"',
    },
  });
}

export function proxy(request: NextRequest) {
  const password = process.env.POLYEDGE_SITE_PASSWORD;

  if (!password) {
    return new NextResponse("Private access has not been configured.", {
      status: 503,
    });
  }

  const authorization = request.headers.get("authorization");

  if (!authorization?.startsWith("Basic ")) {
    return unauthorized();
  }

  try {
    const [providedUsername, providedPassword] = atob(
      authorization.slice("Basic ".length),
    ).split(":");

    if (providedUsername === username && providedPassword === password) {
      return NextResponse.next();
    }
  } catch {
    // A malformed authorization header is treated as an invalid login.
  }

  return unauthorized();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
